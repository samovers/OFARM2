"""Real receipt history from fixed, authenticated pre-repair source bytes.

The base subprocess owns all historical writes and exits before the candidate
opens its function-isolated database. No stored history or guard is patched.
"""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
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


BASE_COMMIT = "47610badaf171bee7ac83c3430bad561073c7e14"
BASE_TREE = "b7e94ea19ad56fe8db9320cadea044263dc37997"


@pytest.fixture(scope="session")
def receipt_base_tree():
    """Use the accepted observation-history archive authentication procedure."""
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
    with TemporaryDirectory(prefix="ofarm-receipt-base-") as directory:
        root, digests = Path(directory), {}
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
def receipt_history(receipt_base_tree):
    from fastapi.testclient import TestClient
    from kernel.legacy_m1.api import create_test_app
    from kernel.runtime_activation import complete_store_startup
    from kernel.tests.conftest import _admin_dsn, _bound_store

    assert sys.version_info[:3] == (3, 12, 13), "history needs pinned CPython 3.12.13"
    root, digests = receipt_base_tree
    with ExitStack() as cleanup:
        def open_history(family, explicit_farm):
            dbname = "ofarm_receipt_history_" + uuid4().hex

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
                [sys.executable, "-I", "-B", str(Path(__file__).resolve()), str(root)],
                input=json.dumps({"dsn": dsn, "digests": digests, "family": family,
                                  "explicitFarm": explicit_farm}), text=True,
                capture_output=True, env=child_env, cwd=root, timeout=120)
            assert child.returncode == 0, child.stderr
            history = json.loads(child.stdout)
            assert history["source"]["commit"] == BASE_COMMIT
            assert history["source"]["tree"] == BASE_TREE
            store = _bound_store(dsn)
            cleanup.callback(store.close)
            complete_store_startup(store)
            client = cleanup.enter_context(TestClient(create_test_app(store, oidc=None)))
            return SimpleNamespace(store=store, client=client, history=history)

        yield open_history


def _base_phase(root, request):
    """Only the imported fixed-base runtime emits the retained history."""
    assert not any(name == "kernel" or name.startswith("kernel.") for name in sys.modules)
    sys.path.insert(0, str(root))
    from fastapi.testclient import TestClient
    from kernel import demo
    from kernel.legacy_m1.api import create_test_app
    from kernel.runtime_activation import complete_store_startup
    from kernel.tests.conftest import _bound_store
    from kernel.tests.test_correction_authorization import _submission
    from kernel.tests.test_review_confirmation import _commit, _snapshot

    store = _bound_store(request["dsn"])
    try:
        complete_store_startup(store)
        demo.bootstrap(store)
        with TestClient(create_test_app(store, oidc=None)) as client:
            env = SimpleNamespace(store=store, client=client)
            submission = _submission(request["family"], demo.FARMER)
            submission["confirmAccept"] = True
            submission["targetScopes"] = [{"scopeType": "FIELD", "scopeRef": demo.FIELD}]
            if request["explicitFarm"]:
                submission["targetScopes"].insert(0, {"scopeType": "FARM", "scopeRef": demo.FARM})
            original = _commit(env, submission)
            assert original["decisionOutcome"] == (
                "PROMOTE_ACCEPTED" if request["family"] == "OPERATION_CLAIM" else "RETAIN_DRAFT")
            matching = _commit(env, deepcopy(submission))
            assert matching["idempotencyDisposition"] == "REPLAY_MATCH_REUSED_RESULT"
            conflicting = deepcopy(submission)
            conflicting["eventTime"] = "2026-06-10T09:01:00Z"
            conflict = _commit(env, conflicting)
            assert conflict["decisionOutcome"] == "DENY"
            assert conflict["idempotencyDisposition"] == "CONFLICTING_REPLAY_BLOCKED"
            cases = {"original": original, "matching": matching, "conflict": conflict}
            for label in ("validation_refusal", "evidence_refusal"):
                refused = deepcopy(submission)
                refused["idempotencyKey"] = "receipt-history:" + uuid4().hex
                if label == "validation_refusal":
                    refused["targetScopes"][-1]["scopeRef"] = "field:fictional.unresolved.history"
                else:
                    refused["evidenceRefs"] = []
                    if request["family"] == "OPERATION_CLAIM":
                        # Existing wrong-kind records pass reference existence
                        # but cannot satisfy durable evidence after validation.
                        refused["evidenceRefs"] = [demo.FARMER]
                        refused["payload"]["evidenceRefs"] = [demo.FARMER]
                        refused["payload"]["executionRecordPayloadId"] = "erp:history." + uuid4().hex
                result = _commit(env, refused)
                assert result["decisionOutcome"] == "RETAIN_DRAFT", result
                gates = store.get_record(result["promotionTraceRef"])["payload"]["gateSequence"]
                validation_passed = any(g["gate"] == "VALIDATION" and g["outcome"] == "PASS"
                                        for g in gates)
                assert validation_passed == (label == "evidence_refusal"), gates
                cases[label] = result
            base_reads = {}
            for label, result in cases.items():
                statuses = [client.get("/records/" + result[key],
                                       headers={"x-acting-party": demo.FARMER}).status_code
                            for key in ("resultId", "promotionTraceRef")]
                assert statuses == ([200, 200] if request["explicitFarm"] else [403, 403])
                base_reads[label] = statuses
            history = {"submission": submission, "cases": cases, "baseReads": base_reads,
                       "snapshot": _snapshot(store)}
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
    print(json.dumps(_base_phase(Path(sys.argv[1]).resolve(), json.load(sys.stdin))))
