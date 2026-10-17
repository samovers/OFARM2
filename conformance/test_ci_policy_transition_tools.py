"""Shared accounting and the actual private supervisor lifecycle."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

import pytest

from conformance import ci_policy_transition_tools as tools

ROOT = Path(__file__).resolve().parent


def _charge_separate_process(path, count):
    budget = tools.RequestBudget("publish", path=path)
    for _ in range(count):
        budget.charge("REST", 1, "fixture")


def test_pool_allocations_preserve_reviewed_whole_grant():
    assert tuple(map(sum, zip(*tools.TOOL_ALLOCATIONS.values()))) == (116, 103)
    assert tuple(map(sum, zip(*tools.POOL_LIMITS.values()))) == (334, 97)


def test_accounting_is_atomic_across_processes_and_retains_terminal_failure(tmp_path):
    tmp_path.chmod(0o700)
    path = tmp_path / "ledger.json"
    budget = tools.RequestBudget("publish", path=path)
    with ProcessPoolExecutor(max_workers=3) as workers:
        futures = [workers.submit(_charge_separate_process, path, 12) for _ in range(3)]
        for future in futures:
            future.result(timeout=20)
    assert budget.used == {"publish": [36, 0]}
    with pytest.raises(tools.TransitionError, match="allowance"):
        budget.charge("REST", 10, "fixture overrun")
    assert budget.used == {"publish": [46, 0]}
    restarted = tools.RequestBudget("publish", path=path)
    with pytest.raises(tools.TransitionError, match="permanently"):
        restarted.assert_healthy()


def test_deleted_state_cannot_restart_budget(tmp_path):
    tmp_path.chmod(0o700)
    path = tmp_path / "ledger.json"
    budget = tools.RequestBudget("conformance", path=path)
    budget.charge("REST", 1, "fixture")
    path.unlink()
    with pytest.raises(tools.TransitionError, match="disappeared"):
        budget.assert_healthy()


def test_changed_lock_cannot_fork_accounting_authority(tmp_path):
    tmp_path.chmod(0o700)
    path = tmp_path / "ledger.json"
    budget = tools.RequestBudget("conformance", path=path)
    lock = tmp_path / "ledger.json.lock"
    lock.rename(tmp_path / "old.lock")
    tools.write_new(lock, b"")
    with pytest.raises(tools.TransitionError, match="lock changed"):
        budget.charge("REST", 1, "fixture")


def test_quota_snapshots_survive_steps_and_never_credit_out_of_order_response(tmp_path):
    tmp_path.chmod(0o700)
    path = tmp_path / "ledger.json"
    budget = tools.RequestBudget("conformance", path=path, clock=lambda: 1000)
    budget.observe_quota("REST", remaining=990, reset=2000, limit=1000)
    budget.observe_quota("REST", remaining=995, reset=2000, limit=1000)
    other = tools.RequestBudget("conformance", path=path, clock=lambda: 1000)
    assert other.quota["REST"]["remaining"] == 990
    other.observe_quota("GraphQL", remaining=900, reset=2000, limit=1000)
    other.require_headroom(future_rest=990, future_graphql=900)
    with pytest.raises(tools.TransitionError, match="insufficient"):
        other.require_headroom(future_rest=991, future_graphql=900)
    with pytest.raises(tools.TransitionError, match="permanently"):
        budget.assert_healthy()


def test_cancellation_counts_two_rest_requests_without_clearing_failure():
    budget = tools.RequestBudget("source-guard")
    budget.fail("fixture failure")
    budget.current_pool = "shared-tools"
    with budget.cancellation():
        budget.charge_transport("own-run-read")
        budget.charge("REST", 1, "own-run-read")
        budget.charge_transport("own-run-cancel")
        budget.charge("REST", 1, "own-run-cancel")
    assert budget.used == {"shared-tools": [2, 0]}
    with pytest.raises(tools.TransitionError, match="permanently"):
        budget.assert_healthy()
    with pytest.raises(tools.TransitionError, match="cancellation"):
        with budget.cancellation():
            budget.charge("REST", 1, "another cancellation")


def test_completed_bytes_are_retained_after_failure_and_trace_omits_secrets():
    budget = tools.RequestBudget("conformance")
    budget.charge_transport("https://fixture.invalid/?token=DO-NOT-RETAIN", bytes=12)
    budget.fail("Bearer DO-NOT-RETAIN")
    with pytest.raises(tools.TransitionError):
        budget.charge_transport(
            "https://fixture.invalid/?token=DO-NOT-RETAIN", requests=0, bytes=19
        )
    assert budget._state["transport"] == {"requests": 1, "bytes": 31}
    assert "DO-NOT-RETAIN" not in tools.canonical(budget._state).decode()


def test_sweep_deadline_is_terminal_and_cannot_be_reset():
    budget = tools.RequestBudget("conformance", monotonic=lambda: 15)
    budget.deadline = 15
    with pytest.raises(tools.TransitionError, match="deadline"):
        budget.remaining_timeout()
    budget.deadline = None
    with pytest.raises(tools.TransitionError, match="permanently"):
        budget.assert_healthy()


@contextmanager
def _running_supervisor(job="conformance"):
    # Unix socket pathname limits are shorter than pytest's macOS temp paths.
    with tempfile.TemporaryDirectory(prefix="of-t-", dir="/tmp") as temporary:
        root = Path(temporary).resolve()
        control = root / "c"
        control.mkdir(mode=0o700)
        for destination, source in (
            ("tools.py", "ci_policy_transition_tools.py"),
            ("node.cjs", "ci_policy_transition_node.cjs"),
            ("execution.py", "ci_policy_transition_execution.py"),
            ("gh_relay.py", "ci_policy_transition_gh_relay.py"),
            ("curl.py", "ci_policy_transition_curl.py"),
        ):
            tools.write_new(control / destination, (ROOT / source).read_bytes())
        github_env = root / "environment"
        startup_environment = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(root),
            "LANG": "C.UTF-8",
            **{
                key: hashlib.sha256((control / name).read_bytes()).hexdigest()
                for name, key in tools.ASSET_ENV.items()
            },
        }
        result = subprocess.run(
            [
                sys.executable,
                str(control / "tools.py"),
                "start",
                "--directory",
                str(control),
                "--job",
                job,
                "--run-id",
                "123",
                "--run-attempt",
                "1",
                "--root-sha",
                "a" * 40,
                "--github-env",
                str(github_env),
            ],
            env=startup_environment,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, result.stderr
        environment = dict(
            line.split("=", 1) for line in github_env.read_text().splitlines()
        )
        environment.update(PATH="/usr/bin:/bin", HOME=str(control), LANG="C.UTF-8")
        config = tools.decode(tools.private_file(control / "config.json"))
        try:
            yield control, config, environment
        finally:
            if control.exists():
                try:
                    tools.finish(environment)
                except tools.TransitionError:
                    pass


def _frame(config, process, sequence, operation, **kwargs):
    return {
        "schema": 1,
        "nonce": config["nonce"],
        "processId": process,
        "sequence": sequence,
        "operation": operation,
        **kwargs,
    }


def _complete_request(
    control,
    config,
    *,
    status=200,
    bucket="REST",
    path="/repos/fictional/example",
    quota=None,
):
    process = str(uuid.uuid4())
    request = process + ":1"

    def send(sequence, operation, **values):
        return tools._exchange(
            control, _frame(config, process, sequence, operation, **values)
        )

    send(0, "open", kind="node", pid=os.getpid(), ppid=os.getppid())
    send(
        1,
        "begin",
        requestId=request,
        method="POST" if bucket == "GraphQL" else "GET",
        host="api.github.com",
        path=path,
        bucket=bucket,
    )
    send(
        2,
        "response",
        requestId=request,
        status=status,
        quota=quota
        or {
            "bucket": bucket,
            "limit": 1000,
            "remaining": 999,
            "reset": int(time.time()) + 3600,
        },
    )
    send(3, "end", requestId=request, bytes=123, complete=True)
    send(4, "close")


def test_real_supervisor_success_drain_and_owned_cleanup():
    with _running_supervisor() as (control, config, environment):
        _complete_request(control, config)
        tools.assert_supervisor(environment, "conformance")
        budget = tools.RequestBudget("conformance", path=control / "ledger.json")
        assert budget.used == {"shared-tools": [1, 0]}
        assert budget._snapshot("transport") == {"requests": 1, "bytes": 123}
        tools.finish(environment)
        assert not control.exists()


@pytest.mark.parametrize("status", [403, 429])
def test_real_supervisor_first_refusal_stays_terminal_after_restart(status):
    with _running_supervisor() as (control, config, environment):
        with pytest.raises(tools.TransitionError):
            _complete_request(control, config, status=status)
        with pytest.raises(tools.TransitionError):
            tools.assert_supervisor(environment, "conformance")
        budget = tools.RequestBudget("conformance", path=control / "ledger.json")
        assert budget.used == {"shared-tools": [1, 0]}
        assert budget.quota["REST"]["remaining"] == 999
        with pytest.raises(tools.TransitionError):
            budget.assert_healthy()
        with pytest.raises(tools.TransitionError):
            tools.finish(environment)
        assert not control.exists()


def test_real_supervisor_missing_completion_refuses_even_after_process_exit():
    with _running_supervisor() as (control, config, environment):
        process = str(uuid.uuid4())
        tools._exchange(
            control,
            _frame(
                config,
                process,
                0,
                "open",
                kind="node",
                pid=os.getpid(),
                ppid=os.getppid(),
            ),
        )
        with pytest.raises(tools.TransitionError):
            tools._exchange(
                control, {"schema": 1, "nonce": config["nonce"], "operation": "check"}
            )


def test_graphql_charges_whole_used_upper_bound_never_snapshot_difference():
    supervisor = tools.Supervisor.__new__(tools.Supervisor)
    supervisor.budget = tools.RequestBudget("conformance")
    supervisor.budget.current_pool = "shared-tools"
    reset = int(time.time()) + 3600
    supervisor.budget.observe_quota("GraphQL", remaining=999, reset=reset, limit=1000)
    prior = supervisor.budget.quota["GraphQL"]
    supervisor.budget.charge("GraphQL", 1, "dispatch")
    supervisor._observe_primary(
        "GraphQL",
        {
            "bucket": "GraphQL",
            "remaining": 996,
            "used": 4,
            "reset": reset,
            "limit": 1000,
        },
        prior,
    )
    assert supervisor.budget.used == {"shared-tools": [0, 4]}


@pytest.mark.parametrize(
    "failure",
    ["missing-prior", "window-change", "contradictory-used", "no-cost", "excess"],
)
def test_real_supervisor_unknown_graphql_cost_cannot_pass(failure):
    supervisor = tools.Supervisor.__new__(tools.Supervisor)
    supervisor.budget = budget = tools.RequestBudget("conformance")
    budget.current_pool = "shared-tools"
    reset = int(time.time()) + 3600
    budget.charge("GraphQL", 1, "dispatch")
    prior = None
    if failure != "missing-prior":
        budget.observe_quota("GraphQL", remaining=999, reset=reset, limit=1000)
        prior = budget.quota["GraphQL"]
    quota = {
        "bucket": "GraphQL",
        "remaining": 998,
        "used": 2,
        "reset": reset,
        "limit": 1000,
    }
    if failure == "window-change":
        quota["reset"] += 3600
    elif failure == "contradictory-used":
        quota["used"] = 3
    elif failure == "no-cost":
        quota.pop("used")
    elif failure == "excess":
        quota.update(remaining=959, used=41)
    with pytest.raises(tools.TransitionError):
        supervisor._observe_primary("GraphQL", quota, prior)


def test_real_supervisor_rejects_changed_bootstrap_before_any_rpc():
    with _running_supervisor() as (control, _config, environment):
        (control / "node.cjs").write_bytes(b"changed")
        with pytest.raises(tools.TransitionError, match="changed trusted"):
            tools.assert_supervisor(environment, "conformance")
        # Restore only to permit authenticated cleanup; a changed file was
        # detected by the client before dispatch, not accepted by the server.
        (control / "node.cjs").write_bytes(
            (ROOT / "ci_policy_transition_node.cjs").read_bytes()
        )


def test_real_supervisor_unknown_transport_is_not_a_generic_proxy():
    with _running_supervisor() as (control, config, _environment):
        process = str(uuid.uuid4())
        tools._exchange(
            control,
            _frame(
                config,
                process,
                0,
                "open",
                kind="node",
                pid=os.getpid(),
                ppid=os.getppid(),
            ),
        )
        with pytest.raises(tools.TransitionError):
            tools._exchange(
                control,
                _frame(
                    config,
                    process,
                    1,
                    "begin",
                    requestId=process + ":1",
                    method="GET",
                    host="example.invalid",
                    path="/",
                    bucket="download",
                ),
            )


def test_external_aliases_cannot_create_new_allowances():
    budget = tools.RequestBudget("external-acceptance")
    for pool in ("shared-tools", "external-acceptance", "source-reader", "publish"):
        budget.current_pool = pool
        budget.charge("REST", 14, "fictional acceptance")
    assert budget.used == {"shared-tools": [56, 0]}
    budget.current_pool = "another-spelling"
    with pytest.raises(tools.TransitionError, match="allowance"):
        budget.charge("REST", 1, "refused")
    assert budget.used == {"shared-tools": [57, 0]}


def test_terminal_completion_keeps_status_bytes_and_rejects_new_dispatch():
    budget = tools.RequestBudget("conformance")
    budget.fail("fictional failure")
    budget.charge_transport("first body chunk", requests=0, bytes=12, completion=True)
    budget.charge_transport("last body chunk", requests=0, bytes=8, completion=True)
    budget.record_outcome("a" * 32, status=429, complete=True)
    budget.record_outcome("b" * 32, status=None, complete=False)
    assert budget._state["transport"]["bytes"] == 20
    assert budget.trace[-2:] == [
        {"requestId": "a" * 32, "status": 429, "complete": True},
        {"requestId": "b" * 32, "status": None, "complete": False},
    ]
    with pytest.raises(tools.TransitionError):
        budget.charge("REST", 1, "new dispatch")


def test_real_supervisor_retains_late_end_after_terminal_status():
    with _running_supervisor() as (control, config, environment):
        process = str(uuid.uuid4())
        request = process + ":1"

        def send(sequence, operation, **fields):
            return tools._exchange(
                control, _frame(config, process, sequence, operation, **fields)
            )

        send(0, "open", kind="node", pid=os.getpid(), ppid=os.getppid())
        send(
            1,
            "begin",
            requestId=request,
            method="GET",
            host="api.github.com",
            path="/repos/fictional/example",
            bucket="REST",
        )
        with pytest.raises(tools.TransitionError):
            send(2, "response", requestId=request, status=429, quota=None)
        with pytest.raises(tools.TransitionError):
            send(3, "end", requestId=request, bytes=19, complete=False)
        ledger = tools.decode(tools.private_file(control / "ledger.json"))
        assert ledger["transport"]["bytes"] == 19
        assert ledger["trace"][-1] == {
            "requestId": request.replace("-", ""),
            "status": 429,
            "complete": False,
        }
        with pytest.raises(tools.TransitionError):
            send(4, "end", requestId=request, bytes=19, complete=False)
        assert (
            tools.decode(tools.private_file(control / "ledger.json"))["transport"][
                "bytes"
            ]
            == 19
        )


def test_supervisor_lifetime_matches_guard_and_binding_jobs():
    assert tools.JOB_LIFETIMES["source-guard"] == 135 * 60
    assert tools.JOB_LIFETIMES["source-gate"] == 5 * 60
    assert tools.JOB_LIFETIMES["publisher-gate"] == 5 * 60
    assert tools.JOB_LIFETIMES["source-admission"] == 10 * 60


def test_start_output_failure_reaps_daemon_and_cleanup_handles_fresh_assets(
    monkeypatch,
):
    from types import SimpleNamespace

    with tempfile.TemporaryDirectory(prefix="of-boot-", dir="/tmp") as temp:
        control = Path(temp).resolve() / "c"
        control.mkdir(mode=0o700)
        for name, key in tools.ASSET_ENV.items():
            source = (
                "ci_policy_transition_node.cjs"
                if name == "node.cjs"
                else "ci_policy_transition_" + name
            )
            tools.write_new(control / name, (ROOT / source).read_bytes())
            monkeypatch.setenv(
                key, hashlib.sha256((control / name).read_bytes()).hexdigest()
            )
        tools.cleanup_start(control)  # A refused start before registration is harmless.
        monkeypatch.setattr(tools, "__file__", str(control / "tools.py"))
        args = SimpleNamespace(
            directory=str(control),
            job="conformance",
            run_attempt=1,
            run_id=123,
            root_sha="a" * 40,
            github_env=str(control),
        )
        with pytest.raises(IsADirectoryError):
            tools.start(args)
        process = tools.decode(tools.private_file(control / "process.json"))
        with pytest.raises((ProcessLookupError, FileNotFoundError)):
            tools._process_identity(process["pid"])
        assert not (control / "control.sock").exists()
        tools.cleanup_start(control)


def test_frozen_factory_loads_only_selected_trusted_native_policy():
    supervisor = tools.Supervisor.__new__(tools.Supervisor)
    supervisor.directory = Path("/tmp")
    root = ROOT.parent
    sha = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    supervisor.config = {"rootSha": sha}
    from conformance import ci_policy_transition_gh_relay as relay

    supervisor._module = lambda name: relay
    policy = supervisor._policy(str(root))
    assert policy == relay.frozen_release_policy()
    supervisor.config = {"rootSha": "0" * 40}
    with pytest.raises(tools.TransitionError, match="wrong trusted"):
        supervisor._policy(str(root))


@pytest.mark.parametrize("status,late", [(403, False), (429, False), (200, True)])
def test_owned_graphql_settles_known_upper_bound_after_throttle_or_other_failure(status, late):
    with _running_supervisor() as (control, config, _environment):
        supervisor = tools.Supervisor(control, config)
        reset = int(time.time()) + 3600
        supervisor.budget.observe_quota("GraphQL", remaining=980, reset=reset, limit=1000)
        process = str(uuid.uuid4())
        request = process + ":1"
        def send(sequence, operation, **fields):
            return supervisor.accept(_frame(config, process, sequence, operation, **fields), trusted_kind="gh")
        assert send(0, "open", kind="gh", pid=os.getpid(), ppid=os.getppid())["accepted"]
        assert send(1, "begin", requestId=request, method="POST", host="api.github.com", path="/graphql", bucket="GraphQL")["accepted"]
        if late:
            supervisor.budget.fail("another already-started request failed")
        reply = send(2, "response", requestId=request, status=status,
            quota={"bucket":"GraphQL", "remaining":979, "used":21, "reset":reset, "limit":1000})
        assert reply["accepted"] is False
        assert supervisor.budget.used == {"shared-tools":[0,21]}
        assert supervisor.budget.quota["GraphQL"]["remaining"] == 979
        bound = next(item for item in supervisor.budget.trace if item.get("costMode") == "absolute-used-upper-bound")
        assert bound["actualCost"] is None and bound["chargedBound"] == 21
        assert send(3, "end", requestId=request, bytes=17, complete=True)["accepted"] is False
        assert supervisor.budget._snapshot("transport")["bytes"] == 17
        with pytest.raises(tools.TransitionError):
            supervisor.budget.charge("GraphQL", 1, "new dispatch")


@pytest.mark.parametrize("status", [200, 403, 429])
def test_owned_graphql_settles_historical_bound_after_reset_without_headroom(status):
    with _running_supervisor() as (control, config, _environment):
        supervisor = tools.Supervisor(control, config)
        reset = 1001
        now = [reset - 1]
        supervisor.budget.clock = lambda: now[0]
        supervisor.budget.observe_quota("GraphQL", remaining=980, reset=reset, limit=1000)
        prior = supervisor.budget.quota["GraphQL"]
        process = str(uuid.uuid4())
        request = process + ":1"

        def send(sequence, operation, **fields):
            return supervisor.accept(
                _frame(config, process, sequence, operation, **fields), trusted_kind="gh"
            )

        assert send(0, "open", kind="gh", pid=os.getpid(), ppid=os.getppid())["accepted"]
        assert send(1, "begin", requestId=request, method="POST", host="api.github.com",
                    path="/graphql", bucket="GraphQL")["accepted"]
        assert supervisor.clients[process]["requests"][request]["priorQuota"] == prior
        now[0] = reset + 1
        reply = send(2, "response", requestId=request, status=status,
                     quota={"bucket": "GraphQL", "remaining": 979, "used": 21,
                            "reset": reset, "limit": 1000})
        assert reply["accepted"] is False
        assert supervisor.budget.used == {"shared-tools": [0, 21]}
        assert supervisor.budget.quota["GraphQL"] == prior
        costs = [item for item in supervisor.budget.trace if "costMode" in item]
        assert len(costs) == 1
        assert costs[0]["costMode"] == "absolute-used-upper-bound"
        assert costs[0]["actualCost"] is None and costs[0]["chargedBound"] == 21
        assert costs[0]["reset"] == reset < now[0]
        assert send(3, "end", requestId=request, bytes=17, complete=True)["accepted"] is False
        assert supervisor.budget._snapshot("transport")["bytes"] == 17
        assert supervisor.budget._snapshot("failed") is True
        with pytest.raises(tools.TransitionError):
            supervisor.budget.require_headroom(future_rest=0, future_graphql=0)
        assert send(4, "begin", requestId=process + ":2", method="POST",
                    host="api.github.com", path="/graphql", bucket="GraphQL")["accepted"] is False
        assert supervisor.budget.used == {"shared-tools": [0, 21]}


def test_unknown_graphql_cost_is_explicit_after_failure():
    supervisor = tools.Supervisor.__new__(tools.Supervisor)
    supervisor.budget = tools.RequestBudget("conformance")
    supervisor.budget.current_pool = "shared-tools"
    supervisor.budget.charge("GraphQL", 1, "reservation before dispatch")
    supervisor.budget.fail("fictional transport failure")
    with pytest.raises(tools.TransitionError):
        supervisor._observe_primary("GraphQL", None)
    assert supervisor.budget.used == {"shared-tools":[0,1]}
    assert supervisor.budget.trace[-1] == {"bucket":"GraphQL", "costMode":"unknown", "actualCost":None, "chargedBound":None}


def test_every_generated_job_lifetime_matches_its_supervisor():
    import re
    def generated_timeouts(name):
        document = (ROOT.parent / ".github/workflows" / name).read_text().split("\njobs:\n", 1)[1]
        jobs = {}
        for match in re.finditer(r"^  ([a-z][a-z0-9-]*):\n(.*?)(?=^  [a-z][a-z0-9-]*:|\Z)", document, re.M | re.S):
            timeouts = re.findall(r"^    timeout-minutes: ([1-9][0-9]*)$", match[2], re.M)
            assert len(timeouts) == 1
            jobs[match[1]] = int(timeouts[0])
        return jobs
    source = generated_timeouts("ci-policy-transition-source.yml")
    publication = generated_timeouts("ci-policy-transition-publication.yml")
    pairs = [(source, "baseline-admission", "source-gate"), (source, "conformance", "conformance"),
        (source, "native-verifier", "native-amd64"), (source, "native-verifier", "native-arm64"),
        (source, "source-guard", "source-guard"), (source, "publication-handoff", "handoff"),
        (publication, "publisher-binding", "publisher-gate"), (publication, "source-admission", "source-admission"),
        (publication, "publish", "publish"), (publication, "publisher-guard", "publisher-guard"),
        (publication, "publication-seal", "seal")]
    assert {owner for _, _, owner in pairs} == set(tools.JOB_LIFETIMES) - {"external-acceptance"}
    for jobs, job, owner in pairs:
        assert tools.JOB_LIFETIMES[owner] == jobs[job] * 60


def test_source_admission_control_stays_alive_after_five_minutes(monkeypatch):
    with _running_supervisor("source-admission") as (control, config, _environment):
        supervisor = tools.Supervisor(control, config)
        started = supervisor.started
        monkeypatch.setattr(tools.time, "monotonic", lambda: started + 360)
        supervisor._custody()
        supervisor.budget.assert_healthy()
        monkeypatch.setattr(tools.time, "monotonic", lambda: started + 601)
        with pytest.raises(tools.TransitionError, match="lifetime"):
            supervisor._custody()
