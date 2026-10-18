"""Offline generated-policy integration; tool internals and hosted runs are separate.

Complete fictional artifact bytes reach the unchanged substantive validators.
The generated command sequence drives the real transition core/publication paths;
there are no substituted validator results. Recorded tool primary costs are
replayed through the real reader and owning ledger into the same provider quota
window. Tool internals/bytes remain separate controls; this is not a hosted
execution or a measurement of baseline elapsed time.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
import copy
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import re
import urllib.error
import urllib.parse
from unittest import mock

import pytest

from conformance import ci_policy_transition as transition
from conformance import ci_policy_transition_publication as publication
from conformance import ci_policy_transition_workflows as workflows
from conformance import test_ci_policy_transition as core_fixture
from conformance import test_ci_policy_transition_publication as artifact_fixture


# Additional primary traffic from the measured pinned Action/gh/curl controls.
# Conformance: 17 gh REST + 2 Action REST, and one gh GraphQL request charged
# conservatively at 21 points (its actual cost was not reported). Native jobs:
# two Action REST each. Other jobs' tools measured zero *additional primary*
# calls; their ticket/artifact downloads already execute below. This is not a
# claim that non-primary transport or provider/dependency traffic is zero.
# Evidence: full-native-reset-window-final.json SHA256
# 16b45bfb8cbd30868e9715c7d90fae125c5bf478654903399f1702dcf21a58b2;
# final-production-node-owning-jobs-index-04.json SHA256
# 8728e135476ac7b0ef9d9eb6d3912190c24c3995d036c4255a106fe1bb32502e.
MEASURED_TOOL_PRIMARY = {"conformance": (19, 21), "native-amd64": (2, 0), "native-arm64": (2, 0)}
TOOL_QUERY = "query FixtureToolCost { rateLimit { cost limit remaining resetAt } }"


class PipelineProvider(core_fixture.Provider):
    def __init__(self, *, policy=None, grant=None):
        # The unchanged native identity policy fixes the repository coordinate.
        # Keep that coordinate while all runs, messages, tokens and bytes remain
        # fictional local inputs; never relax the substantive builder validator.
        if policy is None:
            policy, grant = core_fixture.policy_and_grant()
        policy["repository"]["name"] = artifact_fixture.baseline_fixture.REPOSITORY
        grant["repository"] = policy["repository"]["name"]
        with mock.patch.object(core_fixture, "policy_and_grant", return_value=(policy, grant)):
            super().__init__(publisher=True)
        self.source_artifacts = []
        self.published_artifacts = []
        self.payloads = {}
        self.source_graph = None
        self.readers = {}
        self.observations = []
        self.source_guard_complete = False
        self.publisher_guard_complete = False
        self.source_complete_at = None
        self.publisher_complete_at = None
        self.publisher_run_complete = False
        self.sleep_callback = None
        self.origin = self.now
        self.window_offset = 0
        self.window_index = 0
        self.window_rest_start = 0
        self.window_graph_start = 0
        self.tool_replays = {}
        self.tool_replay_transports = {}

    def restart_observations(self, *, offset=0):
        self.calls, self.rest, self.points, self.observations, self.readers = [], 0, 0, [], {}
        self.now = core_fixture.NOW
        self.origin = self.now
        self.window_offset = offset
        self.window_index = 0
        self.window_rest_start = self.window_graph_start = 0
        self.rest_remaining = self.graph_remaining = 1000
        self.reset = int(self.origin.timestamp()) + (3600-offset)
        self.tool_replays = {}
        self.tool_replay_transports = {}

    def _window(self):
        while self.now.timestamp() >= self.reset:
            self.window_index += 1
            self.reset += 3600
            self.window_rest_start, self.window_graph_start = self.rest, self.points
        self.rest_remaining = 1000 + self.window_rest_start
        self.graph_remaining = 1000 + self.window_graph_start

    def jobs(self, role):
        if role == "source" and self.source_complete_at is not None:
            self.producers_complete = self.now >= self.source_complete_at
        if role == "publisher" and self.publisher_complete_at is not None:
            self.producers_complete = self.now >= self.publisher_complete_at
        result = super().jobs(role)
        for job in result["jobs"]:
            complete = (job["name"] == "source guard" and self.source_guard_complete
                or job["name"] == "publisher guard" and self.publisher_guard_complete
                or role == "source" and self.publisher
                or role == "publisher" and self.publisher_run_complete)
            if complete:
                job.update(status="completed", conclusion="success")
        return result

    def run(self, role):
        result = super().run(role)
        if role == "publisher":
            result["created_at"] = self.publisher_created
            if self.publisher_run_complete:
                result.update(status="completed", conclusion="success")
        return result

    @property
    def publisher_created(self):
        return getattr(self, "_publisher_created", "2030-01-01T00:00:03Z")

    def reader(self, phase):
        job = transition.PHASE_JOBS[phase]
        if job not in self.readers:
            budget = transition.RequestBudget(job, clock=lambda: self.now.timestamp(),
                monotonic=lambda: (self.now-self.origin).total_seconds())
            self.readers[job] = transition.ApiReader("fictional-workflow-token", budget=budget,
                opener=lambda request, timeout: self.route(request, timeout, job))
        return self.readers[job]

    def route(self, request, timeout, job):
        self._window()
        url = urllib.parse.urlsplit(request.full_url)
        path = url.path.removeprefix("/repos/" + self.grant["repository"])
        self.observations.append({"job": job, "pool": self.readers[job].budget.current_pool,
            "at": core_fixture.stamp(self.now), "window": self.window_index,
            "method": request.get_method(), "path": path,
            "transport": "GitHub-primary" if url.netloc == "api.github.com" else "artifact-blob"})
        if url.netloc == "fictional.blob.core.windows.net":
            assert request.get_header("Authorization") is None
            return core_fixture.Response(request.full_url, self.payloads[int(path.rsplit("/", 1)[1])], {})
        extra = None
        if path.startswith("/fixture-tool/"):
            extra = {"fixture": "recorded tool primary request"}
        elif path == "/graphql" and json.loads(request.data)["query"] == TOOL_QUERY:
            cost = MEASURED_TOOL_PRIMARY[job][1]
            self.points += cost
            return core_fixture.Response(request.full_url, transition.canonical_json({"data": {"rateLimit": {
                "cost": cost, "limit": 1000, "remaining": self.graph_remaining-self.points,
                "resetAt": core_fixture.stamp(datetime.fromtimestamp(self.reset, timezone.utc))}}}), {})
        elif self.source_graph is not None and request.full_url in self.source_graph.documents:
            extra = copy.deepcopy(self.source_graph.documents[request.full_url])
            if path.startswith("/git/commits/"):
                extra["parents"] = [{"sha": self.grant["baseSha"]}, {"sha": self.grant["headSha"]}]
        elif self.source_graph is not None and request.full_url in self.source_graph.blobs:
            extra = self.source_graph.blobs[request.full_url]
        elif path in {"/actions/runs/201/artifacts", "/actions/runs/202/artifacts"}:
            items = self.source_artifacts if "/201/" in path else self.published_artifacts
            extra = {"total_count": len(items), "artifacts": [artifact_fixture._provider(ref) for ref in items]}
        elif re.fullmatch(r"/actions/artifacts/[1-9][0-9]*", path):
            identity = int(path.rsplit("/", 1)[1])
            extra = artifact_fixture._provider(next(ref for ref in [*self.source_artifacts, *self.published_artifacts]
                if ref["artifactId"] == identity))
        elif re.fullmatch(r"/actions/artifacts/[1-9][0-9]*/zip", path):
            self.rest += 1
            headers = self._headers()
            headers["Location"] = "https://fictional.blob.core.windows.net/artifacts/" + path.split("/")[-2]
            raise urllib.error.HTTPError(request.full_url, 302, "fictional signed redirect", headers, io.BytesIO(b""))
        if extra is not None:
            self.rest += 1
            payload = extra if isinstance(extra, bytes) else transition.canonical_json(extra)
            return core_fixture.Response(request.full_url, payload, self._headers())
        return super().opener(request, timeout)

    def _headers(self):
        return {"X-RateLimit-Remaining": str(self.rest_remaining-self.rest),
            "X-RateLimit-Reset": str(self.reset), "X-RateLimit-Limit": "1000", "X-RateLimit-Resource": "core"}

    def replay_tools(self, phase):
        """Charge recorded primary costs once, before sibling guard observations."""
        job = transition.PHASE_JOBS[phase]
        assert job not in self.tool_replays
        counts = MEASURED_TOOL_PRIMARY.get(job, (0, 0))
        reader = self.reader(phase)
        before = reader.budget._snapshot("transport")
        with reader.pool("shared-tools"):
            for number in range(counts[0]):
                reader(f"/repos/{self.grant['repository']}/fixture-tool/{job}/{number}")
            if counts[1]:
                reader.graphql(TOOL_QUERY, {})
        self.tool_replays[job] = list(counts)
        after = reader.budget._snapshot("transport")
        self.tool_replay_transports[job] = {key: after[key]-before[key] for key in before}

    def sleep(self, seconds):
        self.now += timedelta(seconds=seconds)
        if self.sleep_callback is not None:
            self.sleep_callback()

    def bind_publisher(self, comment):
        self.publisher = True
        self.producers_complete = False
        self._publisher_created = core_fixture.stamp(self.now)
        comment = copy.deepcopy(comment)
        comment["created_at"] = comment["updated_at"] = core_fixture.stamp(self.now)
        self.comments.append(comment)
        self.event, self.context = self.push("publisher")


class StaggeredPipelineProvider(PipelineProvider):
    """Two fictional quota windows, each charged for all observed work.

    This models nonmonotonic reset observations without claiming a provider
    cause. It neither reserves quota nor assumes that another caller is quiet.
    """
    def __init__(self):
        self._restart_quota_history()
        super().__init__()

    def _restart_quota_history(self):
        self.quota_history = {"REST": [], "GraphQL": []}
        self.quota_seen = {"REST": 0, "GraphQL": 0}
        self.quota_observations = {"REST": [], "GraphQL": []}

    def restart_observations(self, *, offset=0):
        super().restart_observations(offset=offset)
        self._restart_quota_history()

    def quota_facts(self, bucket):
        now = int(self.now.timestamp())
        total = self.rest if bucket == "REST" else self.points
        self.quota_history[bucket].append((now, total-self.quota_seen[bucket]))
        self.quota_seen[bucket] = total
        shift = 299 if len(self.quota_observations[bucket]) % 2 else 0
        anchor = int(self.origin.timestamp())-self.window_offset
        reset = anchor + ((now-anchor-shift)//3600+1)*3600+shift
        remaining = 1000-sum(cost for at, cost in self.quota_history[bucket]
                             if reset-3600 <= at < reset)
        self.quota_observations[bucket].append({"remaining": remaining, "reset": reset})
        return remaining, reset

    def route(self, request, timeout, job):
        try:
            response = super().route(request, timeout, job)
        except urllib.error.HTTPError as error:
            remaining, reset = self.quota_facts("REST")
            error.headers.update({"X-RateLimit-Remaining": str(remaining), "X-RateLimit-Reset": str(reset)})
            raise
        url = urllib.parse.urlsplit(request.full_url)
        if url.netloc != "api.github.com":
            return response
        payload = response.getvalue()
        headers = dict(response.headers)
        if url.path == "/graphql":
            remaining, reset = self.quota_facts("GraphQL")
            body = json.loads(payload)
            body["data"]["rateLimit"].update(remaining=remaining,
                resetAt=core_fixture.stamp(datetime.fromtimestamp(reset, timezone.utc)))
            payload = transition.canonical_json(body)
            headers.pop("Content-Length", None)
        else:
            remaining, reset = self.quota_facts("REST")
            headers.update({"X-RateLimit-Remaining": str(remaining), "X-RateLimit-Reset": str(reset)})
        response.close()
        return core_fixture.Response(request.full_url, payload, headers, status=response.status)


def generated_operations():
    root = Path(__file__).resolve().parents[1]
    generated = workflows.generate((root / workflows.SOURCE_INPUT).read_bytes(),
        (root / workflows.PUBLICATION_INPUT).read_bytes(), consumer_pr=413)
    result = {}
    for content, jobs in ((generated.source, ("baseline-admission", "conformance", "native-verifier", "source-guard", "publication-handoff")),
            (generated.publication, ("publisher-binding", "source-admission", "publish", "publisher-guard", "publication-seal"))):
        _prefix, body = workflows._jobs(content.decode(), jobs)
        for job, text in body.items():
            _header, steps = workflows._steps(text)
            operations = []
            for step in steps:
                if re.search(r"(?:\.baseline-admission-policy|\.publication-policy|\.transition-policy)/conformance/ci_policy_transition.py\s*\n", step):
                    operation = re.search(r"--operation ([a-z-]+)", step).group(1)
                    phase = re.search(r"--phase ([^\n]+)", step).group(1).strip()
                    operations.append((operation, phase))
            result[job] = operations
    return result


def complete_fixture(directory, *, provider=None, policy_root=None):
    provider = provider or PipelineProvider()
    initial, _reader = core_fixture.validate(provider, "publisher-gate")
    def ticket_created(refs, _ticket):
        ref = refs[-1]
        payload = transition.parse_record(provider.comments[-1]["body"], "publisher")
        payload["ticket"] = {"id": ref["artifactId"], "digest": ref["digest"]}
        provider.comments[-1]["body"] = transition.record_body("publisher", payload)
        provider.source_artifacts = refs
        return core_fixture.validate(provider, "publisher-gate")[0]
    baseline = artifact_fixture.baseline_fixture
    with mock.patch.object(baseline, "REPOSITORY", provider.grant["repository"]), \
            mock.patch.object(baseline, "HEAD_SHA", provider.grant["mergeSha"]), \
            mock.patch.object(baseline, "SOURCE_RUN_ID", 201), \
            mock.patch.object(baseline, "PUBLISHER_RUN_ID", 202):
        chain = artifact_fixture._complete_chain(directory, live=initial,
            policy_root=policy_root, ticket_created=ticket_created)
    publisher_comment = provider.comments.pop()
    provider.publisher = False
    provider.event, provider.context = provider.push("source")
    provider.source_graph = chain["graph"]
    provider.payloads = chain["payloads"]
    provider.source_artifacts = chain["source_refs"][:-1]
    provider.published_artifacts = []
    provider.restart_observations()
    return provider, chain, publisher_comment


def operation(provider, directory, op, phase, chain, *, guard_seconds=0):
    reader = provider.reader(phase)
    if op == "admit":
        if phase in {"source-gate", "publisher-gate"}:
            _grant, live = transition.discover_binding(provider.policy, reader,
                role="source" if phase == "source-gate" else "publisher", event=provider.event,
                job_context=provider.context, clock=lambda: provider.now, sleep=provider.sleep)
        else:
            live = transition.validate_live(provider.policy, provider.grant, reader, phase=phase,
                now=provider.now, event=provider.event, job_context=provider.context,
                expected_bindings=provider.bindings())
        transition.require_quota_headroom(reader, provider.grant, phase, now=provider.now)
        return live
    if op == "guard":
        if phase == "source-guard":
            provider.source_complete_at = provider.now+timedelta(seconds=guard_seconds)
        else:
            provider.publisher_complete_at = provider.now+timedelta(seconds=guard_seconds)
        live = transition.run_guard(provider.policy, provider.grant, reader, phase=phase,
            event=provider.event, job_context=provider.context, expected_bindings=provider.bindings(),
            clock=lambda: provider.now, monotonic=lambda: (provider.now-provider.origin).total_seconds(), sleep=provider.sleep)
        if phase == "source-guard":
            provider.source_guard_complete = True
        else:
            provider.publisher_guard_complete = True
        return live
    args = argparse.Namespace(operation=op, phase=phase, event=provider.event, job_context=provider.context,
        transition_bindings=provider.bindings(), github_output=None, evidence_output=None,
        ticket_output=directory / "actual-ticket.json", ticket=directory / "actual-ticket.json",
        publication_receipt_output=directory / "actual-receipt.json",
        published_artifacts_input=directory / "upload-outputs.json")
    with mock.patch.object(transition, "utcnow", lambda: provider.now):
        result = publication.run_operation(args, policy=provider.policy, grant=provider.grant, reader=reader)
    if op != "resolve":
        transition.require_quota_headroom(reader, provider.grant, phase, now=provider.now)
    return result


def download(provider, phase, reference, directory, label):
    reader = provider.reader(phase)
    output = directory / label
    with reader.pool("shared-tools"):
        publication.download_artifact(reference=reference, repository=provider.grant["repository"],
            api_url="https://api.github.com", token=reader.token, output_directory=output,
            archive_path=directory / (label + ".zip"), response_factory=reader.artifact_response)
    return output


def run_pipeline(directory, *, offset=0, source_seconds=3600, publish_seconds=2700,
                 provider=None, policy_root=None):
    provider, chain, publisher_comment = complete_fixture(directory / "fixtures",
        provider=provider, policy_root=policy_root)
    provider.restart_observations(offset=offset)
    operations = generated_operations()
    for op, phase in operations["baseline-admission"]:
        operation(provider, directory, op, phase, chain)
    provider.replay_tools("source-gate")
    for job in ("conformance", "native-verifier"):
        for op, phase in operations[job]:
            if "matrix.architecture" in phase:
                for architecture in ("amd64", "arm64"):
                    operation(provider, directory, op, "native-"+architecture, chain)
                    provider.replay_tools("native-"+architecture)
            else:
                operation(provider, directory, op, phase, chain)
                provider.replay_tools(phase)
    for op, phase in operations["source-guard"]:
        operation(provider, directory, op, phase, chain, guard_seconds=source_seconds)
    for op, phase in operations["publication-handoff"]:
        result = operation(provider, directory, op, phase, chain)
        if op == "handoff":
            assert result == chain["ticket"]
    provider.source_artifacts = chain["source_refs"]
    provider.now += timedelta(minutes=10)
    provider.bind_publisher(publisher_comment)
    # Artifact metadata is rebuilt with the real later immutable binding. The
    # source ticket never depends on that future publisher binding.
    for op, phase in operations["publisher-binding"]:
        operation(provider, directory, op, phase, chain)
    for op, phase in operations["source-admission"]:
        operation(provider, directory, op, phase, chain)
        if op == "resolve":
            download(provider, "source-admission", chain["source_refs"][-1], directory, "source-admission-ticket")
    published_ran = False
    def publication_work():
        nonlocal published_ran
        if published_ran:
            return
        published_ran = True
        for op, phase in operations["publish"]:
            live = operation(provider, directory, op, phase, chain)
            if op == "resolve":
                download(provider, "publisher-start", chain["source_refs"][-1], directory, "publisher-ticket")
            if phase == "publisher-start":
                inputs = {ref["name"]: download(provider, phase, ref, directory, "download-"+ref["name"])
                          for ref in chain["source_refs"][:-1]}
                reader = provider.reader(phase)
                with reader.pool("source-reader"):
                    staged = publication.reconstruct_source(inputs=inputs, output=directory / "actual-staged",
                        repository=provider.grant["repository"], merge_sha=provider.grant["mergeSha"],
                        source_run_id=201, token=reader.token, source_response_factory=reader.response,
                        policy_root=chain["policy"])
                chain["actual-staged"] = staged
                # Re-authenticate the existing complete fixture bytes against
                # these newly reconstructed substantive results before use.
                context = publication.publication_context(source=live["source"], publisher=live["publisher"], source_artifacts=chain["source_refs"])
                publication.validate_published(published=chain["published"], reconstructed=staged,
                    admission=live["admissionEvidence"], context=context,
                    published_artifacts=chain["published_refs"], scratch=directory / "publisher-validation",
                    repository=provider.grant["repository"], merge_sha=provider.grant["mergeSha"],
                    source_run_id=201, policy_root=chain["policy"])
            if phase == "prepublish":
                provider.published_artifacts = chain["published_refs"][:-1]
                for ref in chain["published_refs"]:
                    if ref["name"] in {"native-verifier-amd64", "native-verifier-arm64"}:
                        download(provider, "publisher-start", ref, directory, "reauthenticated-"+ref["name"])
            if phase == "preindex":
                provider.published_artifacts = chain["published_refs"]
    provider.sleep_callback = publication_work
    for op, phase in operations["publisher-guard"]:
        operation(provider, directory, op, phase, chain, guard_seconds=publish_seconds)
    provider.sleep_callback = None
    assert published_ran
    (directory / "upload-outputs.json").write_bytes(publication._canonical([
        {key: ref[key] for key in ("artifactId", "digest", "name")} for ref in chain["published_refs"]]))
    for op, phase in operations["publication-seal"]:
        receipt = operation(provider, directory, op, phase, chain)
        if op == "resolve":
            download(provider, "seal-start", chain["source_refs"][-1], directory, "seal-ticket")
    assert receipt["schemaVersion"] == publication.RECEIPT_SCHEMA
    provider.publisher_run_complete = True
    provider.published_artifacts = [*chain["published_refs"], chain["receipt_ref"]]
    chain["actual-receipt"] = receipt
    assert receipt == chain["receipt"]
    return provider, chain, operations


def test_generated_policy_pipeline_reaches_real_validators_and_records_every_api_pool(tmp_path):
    provider, chain, operations = run_pipeline(tmp_path)
    assert chain["actual-staged"]["review-baseline"].is_dir()
    assert operations["publish"] == [("resolve", "publisher-resolve"), ("publish", "publisher-start"),
        ("publish", "prepublish"), ("publish", "preindex")]
    assert provider.readers["publish"].budget.used["source-reader"] == [12, 0]
    for job, reader in provider.readers.items():
        for pool, used in reader.budget.used.items():
            assert all(used[index] <= reader.budget.limits(pool)[index] for index in (0, 1))
        assert job != "external-acceptance" or reader.budget.used[job] == [12, 1]
    assert (tmp_path / "actual-receipt.json").is_file()


@pytest.mark.parametrize("offset", [1, 60, 119, 120, 1799, 3599])
def test_generated_policy_positive_preserves_quota_across_reset_positions(tmp_path, offset):
    provider, _chain, _operations = run_pipeline(tmp_path, offset=offset)
    assert provider.window_index >= 1
    assert {job: provider.readers[job].budget.used["shared-tools"] for job in MEASURED_TOOL_PRIMARY} == {
        job: list(counts) for job, counts in MEASURED_TOOL_PRIMARY.items()}
    assert sum(row["path"].startswith("/fixture-tool/") for row in provider.observations) == 23
    assert all(reader.budget.quota["REST"]["remaining"] >= 0 for reader in provider.readers.values())


@pytest.mark.parametrize("offset,source_minutes,publisher_minutes", [(1, 60, 45), (120, 60, 45),
    (3599, 60, 45), (1799, 133, 57)])
def test_generated_policy_preserves_each_staggered_window_with_all_tool_traffic(
        tmp_path, offset, source_minutes, publisher_minutes):
    provider, chain, _operations = run_pipeline(tmp_path, offset=offset,
        source_seconds=source_minutes*60, publish_seconds=publisher_minutes*60,
        provider=StaggeredPipelineProvider())
    assert chain["actual-receipt"] == chain["receipt"]
    assert sum(row["path"].startswith("/fixture-tool/") for row in provider.observations) == 23
    assert provider.tool_replays["conformance"] == [19, 21]
    for bucket, observations in provider.quota_observations.items():
        assert any(new["reset"] < old["reset"] for old, new in zip(observations, observations[1:]))
        assert len({row["reset"] for row in observations}) >= 4
        for reader in provider.readers.values():
            assert len(reader.budget.quota_constraints[bucket]) <= 2
            assert reader.budget._snapshot("primaryRequests") == {}
            reader.budget.assert_healthy()


@pytest.mark.parametrize("counts", [(21, 21), (19, 41)])
def test_replayed_tool_traffic_cannot_exceed_its_owning_share(tmp_path, counts):
    provider = PipelineProvider()
    with mock.patch.dict(MEASURED_TOOL_PRIMARY, {"conformance": counts}):
        with pytest.raises(transition.TransitionError, match="owned request allowance"):
            run_pipeline(tmp_path, offset=1, provider=provider)
    with pytest.raises(transition.TransitionError):
        provider.readers["conformance"].budget.assert_healthy()
    assert not (tmp_path / "actual-ticket.json").exists()
    assert not (tmp_path / "actual-receipt.json").exists()


def test_completed_tick_does_not_credit_ambient_consumption_or_active_sibling_allowances(tmp_path):
    class AmbientProvider(PipelineProvider):
        def sleep(self, seconds):
            super().sleep(seconds)
            self.rest += 100  # Another caller in the same provider window.
    provider = AmbientProvider()
    with pytest.raises(transition.TransitionError, match="headroom|quota"):
        run_pipeline(tmp_path, offset=1, provider=provider)
    assert provider.cancelled == [201]
    assert provider.tool_replays["conformance"] == [19, 21]
    assert not (tmp_path / "actual-ticket.json").exists()
    assert not (tmp_path / "actual-receipt.json").exists()


def test_long_generated_guards_share_one_grid_for_every_hour_boundary(tmp_path):
    provider, _chain, _operations = run_pipeline(tmp_path, offset=1799,
        source_seconds=133*60, publish_seconds=57*60)
    ticks = [int(pool.removeprefix("periodic:"))
        for reader in provider.readers.values() for pool in reader.budget.used
        if pool.startswith("periodic:")]
    assert len(ticks) == len(set(ticks))
    assert all(tick % 120 == 0 for tick in ticks)
    ticks.sort()
    # Enumerate every integral second of reset placement across the executed
    # trace, including inclusive endpoints and the source/publisher boundary.
    # The observed complete sweeps, not an assumed count per job, are measured.
    for start in range(ticks[0]-3600, ticks[-1]+1):
        count = bisect_right(ticks, start+3600)-bisect_left(ticks, start)
        assert count <= 31
    for reader in provider.readers.values():
        for pool, used in reader.budget.used.items():
            if pool.startswith("periodic:"):
                assert used[0] <= 15 and used[1] <= 5


@pytest.mark.parametrize("publisher", [False, True])
def test_guard_fixed_ceiling_is_terminal_even_when_provider_completes_at_ceiling(publisher):
    provider = PipelineProvider()
    provider.restart_observations(offset=119)
    if not publisher:
        provider.publisher = False
        provider.comments.pop()
        provider.event, provider.context = provider.push("source")
    phase = "publisher-guard" if publisher else "source-guard"
    duration = (60 if publisher else 135)*60
    if publisher:
        provider.publisher_complete_at = provider.now+timedelta(seconds=duration)
    else:
        provider.source_complete_at = provider.now+timedelta(seconds=duration)
    reader = provider.reader(phase)
    with pytest.raises(transition.TransitionError, match="fixed timeout"):
        transition.run_guard(provider.policy, provider.grant, reader, phase=phase,
            event=provider.event, job_context=provider.context, expected_bindings=provider.bindings(),
            clock=lambda: provider.now, monotonic=lambda: (provider.now-provider.origin).total_seconds(),
            sleep=provider.sleep)
    assert provider.cancelled == [202 if publisher else 201]
    assert (provider.now-provider.origin).total_seconds() == duration
    with pytest.raises(transition.TransitionError):
        reader.budget.assert_healthy()
