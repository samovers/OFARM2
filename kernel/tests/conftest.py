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

import psycopg
import pytest

os.environ.setdefault("OFARM_PG_DBNAME", "ofarm_kernel_test")
TEST_DEPLOYMENT_IMAGE_DIGEST = "sha256:" + "a" * 64
os.environ.setdefault("OFARM_DEPLOYMENT_IMAGE_DIGEST", TEST_DEPLOYMENT_IMAGE_DIGEST)

from kernel import config, demo, manifest  # noqa: E402
from kernel.gates import GatePipeline  # noqa: E402
from kernel.materializer import Materializer  # noqa: E402
from kernel.runtime_activation import complete_store_startup  # noqa: E402
from kernel.runtime_bundle import RuntimeBundleBuilder  # noqa: E402
from kernel.store import Store  # noqa: E402
from kernel.views import OutputGenerator  # noqa: E402

EVIDENCE_DIR = config.PACKAGE_ROOT / "conformance" / "evidence"
PLATFORM_MVP_EVIDENCE_SUITE = manifest.PLATFORM_MVP_TEST_SUITE_REF
_RESULTS: list[dict] = []
_DETAILS: dict[str, dict] = {}


def record_detail(test_id: str, detail: dict) -> None:
    """Tests append structured execution details to the evidence file."""
    _DETAILS.setdefault(test_id, {}).update(detail)


def _admin_dsn() -> str:
    explicit = os.environ.get("OFARM_PG_ADMIN_DSN")
    if explicit:
        return explicit  # CI: service-container postgres database
    socket_dir = os.environ.get("OFARM_PG_SOCKET_DIR", str(config.PACKAGE_ROOT / ".pgrun"))
    port = os.environ.get("OFARM_PG_PORT", "54317")
    user = os.environ.get("OFARM_PG_USER", "ofarm")
    return f"host={socket_dir} port={port} dbname=postgres user={user}"


def _bound_store(dsn: str | None = None) -> Store:
    """Create a test Store from one explicit checked-in bundle selection."""
    return Store(
        dsn=dsn,
        tenant_ref=config.TENANT_REF,
        runtime_bundle=RuntimeBundleBuilder.from_manifest(config.PACKAGE_ROOT).build(),
        active_profile_package_name=config.ACTIVE_PROFILE_PACKAGE_NAME,
        active_descriptor=config.ACTIVE_PROFILE,
    )


@pytest.fixture(scope="session")
def store():
    dbname = os.environ["OFARM_PG_DBNAME"]
    with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
        admin.execute(f'CREATE DATABASE "{dbname}"')
    s = _bound_store()
    complete_store_startup(s)
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


@pytest.fixture
def fresh_env():
    """A FUNCTION-scoped fresh DB + bootstrap, yielding (store, pipeline,
    outputs). For tests that assert farm-GLOBAL derived state (e.g. a passport's
    disputeStatus) and must not see — or leak — session-accumulated state."""
    import uuid as _uuid
    import psycopg.conninfo
    from kernel.gates import GatePipeline
    from kernel.views import OutputGenerator
    base = os.environ.get("OFARM_PG_DBNAME", "ofarm_kernel_test")
    dbname = f"{base[:40]}_iso_{_uuid.uuid4().hex[:8]}"
    with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
        admin.execute(f'CREATE DATABASE "{dbname}"')
    # Build the fresh-DB DSN from the admin DSN's connection params (correct
    # host/port/user/password) with the fresh dbname — NEVER via
    # config.database_dsn(), which returns a FIXED OFARM_PG_DSN verbatim in CI and
    # would silently connect to the shared DB (no isolation).
    params = psycopg.conninfo.conninfo_to_dict(_admin_dsn())
    params["dbname"] = dbname
    s = _bound_store(psycopg.conninfo.make_conninfo(**params))
    complete_store_startup(s)
    demo.bootstrap(s)
    yield s, GatePipeline(s), OutputGenerator(s)
    s.close()
    with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{dbname}"')


def is_platform_mvp_evidence_report(report) -> bool:
    """Only root conformance calls may enter PLATFORM_MVP_EXECUTED_EVIDENCE."""
    node_path = report.nodeid.split("::", 1)[0].replace("\\", "/")
    return report.when == "call" and node_path.endswith("kernel/tests/test_conformance.py")


def pytest_runtest_logreport(report):
    # The evidence file claims the root platform MVP + root conformance
    # regression suite, so it carries root conformance results only. Profile
    # bridge/profile-local engineering tests can run in the same session, but
    # they never masquerade as platform executed evidence.
    if is_platform_mvp_evidence_report(report):
        _RESULTS.append({
            "test": report.nodeid,
            "outcome": report.outcome,
            "durationSeconds": round(report.duration, 3),
        })


def pytest_sessionfinish(session, exitstatus):
    if not _RESULTS:
        return  # no conformance tests ran (e.g. -k filter); nothing to attest
    if os.environ.get("OFARM_DISABLE_PLATFORM_MVP_EVIDENCE") == "1":
        return  # complete review baseline has its own all-test evidence writer
    # The reproducible review-baseline runner redirects this legacy,
    # duration-bearing evidence file into its ignored artifact directory.  A
    # normal pytest invocation retains the historical repository-local path.
    evidence_dir = EVIDENCE_DIR
    configured_dir = os.environ.get("OFARM_PLATFORM_MVP_EVIDENCE_DIR")
    if configured_dir:
        evidence_dir = config.PACKAGE_ROOT / configured_dir
        evidence_dir = evidence_dir.resolve()
        try:
            evidence_dir.relative_to(config.PACKAGE_ROOT.resolve())
        except ValueError as exc:
            raise pytest.UsageError(
                "OFARM_PLATFORM_MVP_EVIDENCE_DIR must stay inside the package root"
            ) from exc
    evidence_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc)
    payload = {
        "suite": PLATFORM_MVP_EVIDENCE_SUITE,
        "executed": True,
        "executedAt": ts.isoformat().replace("+00:00", "Z"),
        "runtimeVersion": config.RUNTIME_VERSION,
        "exitStatus": exitstatus,
        "allPassed": exitstatus == 0 and all(r["outcome"] == "passed" for r in _RESULTS),
        "results": _RESULTS,
        "details": _DETAILS,
        "honestyNote": "This file records an actual executed run against the live "
                       "PostgreSQL store. Design fixtures are never presented as "
                       "executed evidence (AGENTS.md rule 7). All test data is "
                       "fictional and format-true (privacy rule 1).",
    }
    path = evidence_dir / f"platform_mvp_results_{ts.strftime('%Y-%m-%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
