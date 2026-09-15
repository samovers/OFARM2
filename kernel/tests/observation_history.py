"""Real observation history from one fixed, unmodified pre-restriction runtime.

Only the immutable source tree is session-shared. Each caller owns a fresh DB;
the base subprocess exits before the candidate opens it. No accepted row is
fabricated and no candidate protection is disabled.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest


BASE_COMMIT = "9d7541d96bc708e9270b986927d7f4b8a035454f"
BASE_TREE = "63d532112ed7c705997d0d71f5f6d0fec12928f7"


@pytest.fixture(scope="session")
def observation_base_tree():
    """Authenticate all fixed-base files from local Git objects, without fetch."""
    checkout = Path(__file__).resolve().parents[2]
    git_env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)

    def git(*args):
        return subprocess.run(
            ["git", "-c", "core.hooksPath=" + os.devnull, "-c", "core.fsmonitor=false", *args],
            cwd=checkout, env=git_env, check=True, capture_output=True).stdout

    assert git("rev-parse", BASE_COMMIT + "^{commit}").decode().strip() == BASE_COMMIT
    assert git("rev-parse", BASE_COMMIT + "^{tree}").decode().strip() == BASE_TREE
    objects, modes = {}, {}
    for entry in git("ls-tree", "-r", "-z", BASE_COMMIT).split(b"\0"):
        if entry:
            meta, name = entry.split(b"\t", 1)
            mode, kind, oid = meta.decode().split()
            assert mode in {"100644", "100755"} and kind == "blob", entry
            objects[name.decode()] = oid
            modes[name.decode()] = 0o755 if mode == "100755" else 0o644
    with TemporaryDirectory(prefix="ofarm-observation-base-") as directory:
        root = Path(directory)
        digests = {}
        with tarfile.open(fileobj=io.BytesIO(git("archive", BASE_COMMIT))) as archive:
            for member in archive:
                name = PurePosixPath(member.name)
                assert not name.is_absolute() and ".." not in name.parts, member.name
                destination = root.joinpath(*name.parts)
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                assert member.isfile() and member.name in objects, member.name
                assert member.name not in digests, member.name
                data = archive.extractfile(member).read()
                blob = b"blob " + str(len(data)).encode() + b"\0" + data
                assert hashlib.sha1(blob).hexdigest() == objects[member.name], member.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                destination.chmod(modes[member.name])
                digests[member.name] = hashlib.sha256(data).hexdigest()
        assert digests.keys() == objects.keys()
        yield root, digests


@pytest.fixture
def observation_history(observation_base_tree):
    """Return one candidate env per caller, following completed base HTTP setup."""
    from contextlib import ExitStack

    from fastapi.testclient import TestClient
    from kernel.gates import GatePipeline
    from kernel.legacy_m1.api import create_test_app
    from kernel.runtime_activation import complete_store_startup
    from kernel.tests.conftest import _admin_dsn, _bound_store
    from kernel.tests.test_review_confirmation import _assert_prior_records_unchanged, _snapshot

    assert sys.version_info[:3] == (3, 12, 13), "history needs pinned CPython 3.12.13"
    root, digests = observation_base_tree
    with ExitStack() as cleanup:
        def open_history(scenario="original"):
            assert scenario in {"original", "stale", "replay", "field"}
            dbname = "ofarm_obs_history_" + uuid4().hex

            def drop():
                with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
                    admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(dbname)))

            with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
            cleanup.callback(drop)
            params = conninfo_to_dict(_admin_dsn())
            params["dbname"] = dbname
            dsn = make_conninfo(**params)
            child_env = {key: value for key, value in os.environ.items()
                         if not key.startswith("OFARM_")}
            child_env["OFARM_DEPLOYMENT_IMAGE_DIGEST"] = "sha256:" + "a" * 64
            child = subprocess.run(
                [sys.executable, "-I", "-B", str(Path(__file__).resolve()), str(root), scenario],
                input=json.dumps({"dsn": dsn, "digests": digests}), text=True,
                capture_output=True, env=child_env, cwd=root, timeout=120)
            assert child.returncode == 0, child.stderr
            history = json.loads(child.stdout)
            assert history["source"]["commit"] == BASE_COMMIT
            assert history["source"]["tree"] == BASE_TREE
            store = _bound_store(dsn)
            cleanup.callback(store.close)
            complete_store_startup(store)
            pipeline = GatePipeline(store)
            client = cleanup.enter_context(TestClient(create_test_app(store, oidc=None)))

            def preserve_history():
                after = _snapshot(store)
                _assert_prior_records_unchanged(history["snapshot"], after)
                edges = {edge["edge_id"]: edge for edge in after["kernel_edge"]}
                for edge in history["snapshot"]["kernel_edge"]:
                    assert edges[edge["edge_id"]] == edge

            preserve_history()
            cleanup.callback(preserve_history)
            return SimpleNamespace(
                store=store, pipeline=pipeline,
                outputs=pipeline.runtime_services.output_assembler, client=client,
                history=history, **history["actors"])

        yield open_history


def _base_phase(root, scenario, request):
    """Base-only child: accepted outputs come exclusively from real HTTP."""
    assert not any(name == "kernel" or name.startswith("kernel.") for name in sys.modules)
    sys.path.insert(0, str(root))
    from fastapi.testclient import TestClient
    from kernel import demo
    from kernel.legacy_m1.api import create_test_app
    from kernel.runtime_activation import complete_store_startup
    from kernel.tests.conftest import _bound_store
    from kernel.tests import test_correction_authorization as correction
    from kernel.tests.test_review_confirmation import _snapshot

    store = _bound_store(request["dsn"])
    try:
        complete_store_startup(store)
        demo.bootstrap(store)
        with TestClient(create_test_app(store, oidc=None)) as client:
            actors = {
                "author": correction._actor(store, correction.ASSERT_ACTIONS),
                "accept_only": correction._actor(store, ("REVIEW_ACCEPT",)),
                "reviewer": correction._actor(
                    store, (*correction.ASSERT_ACTIONS, *correction.REVIEW_ACTIONS)),
            }
            env = SimpleNamespace(store=store, client=client, **actors)
            original = correction._submission("OBSERVATION_ASSERTION", env.author)
            if scenario == "field":
                original["targetScopes"] = [{"scopeType": "FIELD", "scopeRef": demo.FIELD}]
            assertion = correction._queue(env, original)
            acceptance = correction._acceptance_submission(assertion, env.reviewer)
            accepted = correction._commit(env, acceptance)
            assert accepted["decisionOutcome"] == "PROMOTE_ACCEPTED", accepted
            old = accepted["emittedAcceptedConsequenceRefs"][0]
            history = {
                "scenario": scenario, "actors": actors, "original": original,
                "predecessor": old, "assertion": assertion,
                "queued_acceptance": {"submission": acceptance, "result": accepted},
            }
            if scenario in {"stale", "replay"}:
                pending_correction = correction._correction(original, old)
                history["correction"] = pending_correction
                history["pending_correction"] = correction._queue(env, pending_correction)
            if scenario == "stale":
                history["loser"] = correction._queue(env, correction._correction(original, old))
                winner = correction._review(env, history["pending_correction"])
                assert winner["decisionOutcome"] == "PROMOTE_ACCEPTED", winner
                history["winner"] = winner
            if scenario == "replay":
                history["direct_acceptances"] = {}
                for hint in ("omitted", "null", "self"):
                    direct = correction._submission("OBSERVATION_ASSERTION", env.reviewer)
                    direct["confirmAccept"] = True
                    if hint != "omitted":
                        direct["reviewerPartyRef"] = None if hint == "null" else env.reviewer
                    result = correction._commit(env, direct)
                    assert result["decisionOutcome"] == "PROMOTE_ACCEPTED", result
                    history["direct_acceptances"][hint] = {"submission": direct, "result": result}
                history["direct_acceptance"] = history["direct_acceptances"]["null"]
                history["pending_observation"] = correction._queue(
                    env, correction._submission("OBSERVATION_ASSERTION", env.author))
            history["snapshot"] = _snapshot(store)
        imported = {}
        for name, module in tuple(sys.modules.items()):
            if name == "kernel" or name.startswith("kernel."):
                path = Path(module.__file__).resolve()
                relative = path.relative_to(root).as_posix()
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                assert digest == request["digests"][relative], relative
                imported[relative] = digest
        history["source"] = {"commit": BASE_COMMIT, "tree": BASE_TREE,
                             "importedSources": imported}
        return history
    finally:
        store.close()


if __name__ == "__main__":
    print(json.dumps(_base_phase(Path(sys.argv[1]).resolve(), sys.argv[2], json.load(sys.stdin))))
