"""Conformance-suite harness.

Fresh database per session; results land as a JSON evidence file per run
(canonical runner style). Honest reporting (AGENTS.md rule 7): the evidence
file records what actually executed — failing tests are recorded as failing,
and a design fixture is never presented as executed evidence.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest

os.environ.setdefault("OFARM_PG_DBNAME", "ofarm_kernel_test")

from kernel import config, context, demo  # noqa: E402
from kernel.gates import GatePipeline  # noqa: E402
from kernel.materializer import Materializer  # noqa: E402
from kernel.store import Store  # noqa: E402
from kernel.views import OutputGenerator  # noqa: E402

EVIDENCE_DIR = config.PACKAGE_ROOT / "conformance" / "evidence"
_RESULTS: list[dict] = []
_DETAILS: dict[str, dict] = {}


def record_detail(test_id: str, detail: dict) -> None:
    """Tests append structured execution details to the evidence file."""
    _DETAILS.setdefault(test_id, {}).update(detail)


def _admin_dsn() -> str:
    socket_dir = os.environ.get("OFARM_PG_SOCKET_DIR", str(config.PACKAGE_ROOT / ".pgrun"))
    port = os.environ.get("OFARM_PG_PORT", "54317")
    user = os.environ.get("OFARM_PG_USER", "ofarm")
    return f"host={socket_dir} port={port} dbname=postgres user={user}"


@pytest.fixture(scope="session")
def store():
    dbname = os.environ["OFARM_PG_DBNAME"]
    with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
        admin.execute(f'CREATE DATABASE "{dbname}"')
    s = Store()
    s.migrate()
    context.bootstrap(s)
    demo.bootstrap(s)
    yield s
    s.close()


@pytest.fixture(scope="session")
def pipeline(store):
    return GatePipeline(store)


@pytest.fixture(scope="session")
def outputs(store):
    return OutputGenerator(store)


@pytest.fixture(scope="session")
def materializer(store):
    return Materializer(store)


def pytest_runtest_logreport(report):
    if report.when == "call":
        _RESULTS.append({
            "test": report.nodeid,
            "outcome": report.outcome,
            "durationSeconds": round(report.duration, 3),
        })


def pytest_sessionfinish(session, exitstatus):
    EVIDENCE_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc)
    payload = {
        "suite": "conformance:ofarm2.platform-mvp.tests-1-15.v0_1",
        "executed": True,
        "executedAt": ts.isoformat().replace("+00:00", "Z"),
        "runtimeVersion": "ofarm2-kernel-m1.0",
        "exitStatus": exitstatus,
        "allPassed": exitstatus == 0 and all(r["outcome"] == "passed" for r in _RESULTS),
        "results": _RESULTS,
        "details": _DETAILS,
        "honestyNote": "This file records an actual executed run against the live "
                       "PostgreSQL store. Design fixtures are never presented as "
                       "executed evidence (AGENTS.md rule 7). All test data is "
                       "fictional and format-true (privacy rule 1).",
    }
    path = EVIDENCE_DIR / f"platform_mvp_results_{ts.strftime('%Y-%m-%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
