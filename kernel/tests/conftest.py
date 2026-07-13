"""Conformance-suite harness.

Fresh database per session; results land as a JSON evidence file per run
(canonical runner style). Honest reporting (AGENTS.md rule 7): the evidence
file records what actually executed — failing tests are recorded as failing,
and a design fixture is never presented as executed evidence.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

import psycopg
import psycopg.conninfo
import pytest
from psycopg import sql

os.environ.setdefault("OFARM_PG_DBNAME", "ofarm_kernel_test")

from kernel import config, context, demo, manifest  # noqa: E402
from kernel.contracts import canonical_json  # noqa: E402
from kernel.gates import GatePipeline  # noqa: E402
from kernel.materializer import Materializer  # noqa: E402
from kernel.store import (  # noqa: E402
    Store,
    _RETAINED_GOVERNED_CURSOR_EXECUTE_READ as _CURSOR_EXECUTE_READ,
)
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


def _admin_database_dsn(dbname: str) -> str:
    """Derive one database route from the DDL-capable admin route."""
    params = psycopg.conninfo.conninfo_to_dict(_admin_dsn())
    params["dbname"] = dbname
    return psycopg.conninfo.make_conninfo(**params)


def _store_database_dsn(dbname: str) -> str:
    """Retain the configured Store role/server while selecting an isolated DB."""
    params = psycopg.conninfo.conninfo_to_dict(config.database_dsn())
    params["dbname"] = dbname
    return psycopg.conninfo.make_conninfo(**params)


def _require_same_postgres_server_and_role(
        admin_dsn: str, store_dsn: str) -> None:
    """Prove both routes share one lock namespace and effective DB role."""
    lock_key = uuid.uuid4().int & ((1 << 63) - 1)
    with (
        psycopg.connect(admin_dsn, autocommit=True) as admin,
        psycopg.connect(store_dsn, autocommit=True) as store,
    ):
        admin_user = admin.execute("SELECT CURRENT_USER").fetchone()[0]
        store_user = store.execute("SELECT CURRENT_USER").fetchone()[0]
        if admin_user != store_user:
            raise AssertionError(
                "admin and Store DSNs must use the same PostgreSQL role"
            )
        admin.execute(
            "SELECT pg_catalog.pg_advisory_lock(%s)", (lock_key,)
        )
        try:
            if store.execute(
                    "SELECT pg_catalog.pg_try_advisory_lock(%s)",
                    (lock_key,)).fetchone()[0]:
                store.execute(
                    "SELECT pg_catalog.pg_advisory_unlock(%s)", (lock_key,)
                )
                raise AssertionError(
                    "admin and Store DSNs must reach the same PostgreSQL server"
                )
        finally:
            admin.execute(
                "SELECT pg_catalog.pg_advisory_unlock(%s)", (lock_key,)
            )


def _create_database(dbname: str, *, template: str | None = None) -> None:
    with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
        statement = sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname))
        if template is not None:
            statement += sql.SQL(" TEMPLATE {}").format(sql.Identifier(template))
        admin.execute(statement)


def _drop_fixed_database_if_idle(dbname: str) -> None:
    """Replace the shared test DB without terminating another test process."""
    with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(dbname))
        )


def _drop_database(dbname: str) -> None:
    """Remove an isolated database even if a failed test leaked a connection."""
    with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
        admin.execute(
            "SELECT pg_catalog.pg_terminate_backend(pid) "
            "FROM pg_catalog.pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_catalog.pg_backend_pid()",
            (dbname,),
        )
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(dbname))
        )


def _bootstrap_demo_seed(seed: Store) -> None:
    """Seed through the same independent transaction boundaries as production."""
    if Store._transaction_depth(seed) != 0:
        raise AssertionError("demo seed requires no ambient governed transaction")
    demo.bootstrap(seed)
    if Store._transaction_depth(seed) != 0:
        raise AssertionError("demo seed leaked a governed transaction")


def _activate_cloned_seed_runtime(store: Store, bundle, environment_seal) -> None:
    """Attach one seed-selected runtime to its exact PostgreSQL template clone.

    The production-faithful seed performs live selection, installation, and
    activation once. A physical ``CREATE DATABASE ... TEMPLATE`` clone already
    contains those exact persisted bytes. Each isolated Store still runs the
    production preparation and activation checks; it only skips selecting and
    reinstalling the same runtime a second time.
    """
    if (type(store) is not Store
            or Store._transaction_depth(store) != 0
            or store._runtime_bundle is not None
            or store._runtime_environment_seal is not None
            or store._bootstrap_bundle is not None
            or store._pending_runtime_bundle_activation is not None):
        raise AssertionError(
            "fresh_env runtime activation requires one clean unbound Store"
        )
    if (bundle.construction_mode != "LIVE_CURRENT"
            or bundle._selection_environment_seal is not environment_seal
            or environment_seal.bundle_digest != bundle.digest):
        raise AssertionError(
            "fresh_env template runtime is not one exact live bundle/seal pair"
        )

    activation_token = None
    try:
        with Store.serialized_tx(store) as cur:
            expected_payloads = context._profile_payloads_from_bundle(  # noqa: SLF001
                store, config.ACTIVE_PROFILE, bundle)
            expected_by_id = {
                record_id: (kind, payload, expected_digest)
                for record_id, kind, payload, expected_digest
                in expected_payloads
            }
            if len(expected_by_id) != len(expected_payloads):
                raise AssertionError(
                    "fresh_env template profile payload identities are not unique"
                )
            selection_kinds = (
                "ofarm.referencesnapshot.v0.1",
                "ofarm.activeartifactset.v0.1",
                "ofarm.packactivationset.v0.1",
                "ofarm.agronomiccodebindingprofile.v0.1",
            )
            _CURSOR_EXECUTE_READ(
                cur,
                "SELECT record_id, record_kind, lane, schema_hash, payload, "
                "payload_sha256, tenant_ref, runtime_bundle_digest "
                "FROM ONLY kernel_record "
                "WHERE record_id = ANY(%s) "
                "OR (tenant_ref = %s AND record_kind = ANY(%s)) "
                "ORDER BY record_id",
                (list(expected_by_id), bundle.tenant_ref, list(selection_kinds)),
            )
            actual_rows = {row["record_id"]: row for row in cur.fetchall()}
            if set(actual_rows) != set(expected_by_id):
                raise AssertionError(
                    "fresh_env PostgreSQL clone lacks the exact bundled profile spine"
                )
            for record_id, (kind, payload, expected_digest) in \
                    expected_by_id.items():
                row = actual_rows[record_id]
                contract = store.registry.get(kind)
                if (row["record_kind"] != kind
                        or row["lane"] != "canonical"
                        or row["schema_hash"] != contract.schema_hash
                        or row["tenant_ref"] != bundle.tenant_ref
                        or row["runtime_bundle_digest"] != bundle.digest
                        or row["payload_sha256"] != expected_digest
                        or canonical_json(row["payload"]) != canonical_json(payload)):
                    raise AssertionError(
                        "fresh_env PostgreSQL clone has a byte-mismatched profile "
                        f"instance {record_id!r}"
                    )
            _CURSOR_EXECUTE_READ(
                cur, "SELECT count(*) AS n FROM ONLY reference_snapshot_data")
            if cur.fetchone()["n"] != 0:
                raise AssertionError(
                    "fresh_env seed unexpectedly contains database-origin reference "
                    "data; extend the exact clone comparison before importing it"
                )

            # Reuse the production activation path. It rechecks the current
            # runtime catalog and process seal, verifies the cloned database
            # observation and exact schema, and cold-loads every persisted
            # bundle/component byte before preparing the one-use token.
            with Store._bootstrap_bundle_writes(store, bundle):
                activation_token = Store._prepare_runtime_bundle_binding(
                    store, bundle)
    except BaseException:
        Store._discard_prepared_runtime_bundle_binding(store)
        raise

    try:
        Store._activate_prepared_runtime_bundle(store, activation_token)
    except BaseException:
        Store._discard_prepared_runtime_bundle_binding(store)
        raise
    if (Store._transaction_depth(store) != 0
            or store._runtime_bundle is not bundle
            or store._runtime_environment_seal is not environment_seal
            or store._pending_runtime_bundle_activation is not None
            or store.runtime_bundle_digest != bundle.digest):
        raise AssertionError(
            "fresh_env clone did not activate the exact seed RuntimeBundle"
        )


@pytest.fixture(scope="session")
def _seeded_environment():
    """Build one production-faithful seed and snapshot it before tests mutate it."""
    dbname = os.environ["OFARM_PG_DBNAME"]
    base = os.environ.get("OFARM_PG_DBNAME", "ofarm_kernel_test")
    template_dbname = f"{base[:32]}_iso_seed_{uuid.uuid4().hex[:16]}"
    seed = None
    template_created = False
    try:
        _drop_fixed_database_if_idle(dbname)
        _create_database(dbname)
        store_dsn = _store_database_dsn(dbname)
        _require_same_postgres_server_and_role(
            _admin_database_dsn(dbname), store_dsn)
        seed = Store(dsn=store_dsn)
        seed.migrate()
        context.bootstrap(seed)
        _bootstrap_demo_seed(seed)
        runtime_bundle = seed.runtime_bundle
        runtime_environment_seal = seed._runtime_environment_seal
        if (runtime_bundle._selection_environment_seal is not
                runtime_environment_seal
                or runtime_environment_seal.bundle_digest !=
                seed.runtime_bundle_digest):
            raise AssertionError(
                "production-faithful seed lacks one exact live bundle/seal pair"
            )

        # PostgreSQL requires the source database to have no open sessions.
        # Snapshot before yielding, so later session-scoped test mutations can
        # never enter the private template. Store reconnects lazily on use.
        seed.close()
        _create_database(template_dbname, template=dbname)
        template_created = True
        with psycopg.connect(_admin_dsn(), autocommit=True) as admin:
            admin.execute(
                sql.SQL("ALTER DATABASE {} ALLOW_CONNECTIONS false").format(
                    sql.Identifier(template_dbname)
                )
            )
        yield seed, template_dbname, runtime_bundle, runtime_environment_seal
    finally:
        try:
            if seed is not None:
                seed.close()
        finally:
            if template_created:
                _drop_database(template_dbname)


@pytest.fixture(scope="session")
def store(_seeded_environment):
    return _seeded_environment[0]


@pytest.fixture(scope="session")
def pipeline(store):
    return GatePipeline(store)


@pytest.fixture(scope="session")
def outputs(store):
    return OutputGenerator(store)


@pytest.fixture(scope="session")
def materializer(store):
    return Materializer(store)


@pytest.fixture(scope="session")
def _fresh_env_template(_seeded_environment):
    """Expose the immutable pre-test seed snapshot to isolated clones."""
    return (
        _seeded_environment[1],
        _seeded_environment[2],
        _seeded_environment[3],
    )


@pytest.fixture
def fresh_store(_fresh_env_template):
    """Yield one isolated Store activated from the exact immutable seed clone.

    Every clone re-proves the schema and live RuntimeBundle before use. The seed
    Store is closed before PostgreSQL copies it, and no test can write back into
    the session template or another test's database.
    """
    template_dbname, template_runtime_bundle, template_environment_seal = \
        _fresh_env_template
    base = os.environ.get("OFARM_PG_DBNAME", "ofarm_kernel_test")
    dbname = f"{base[:40]}_iso_{uuid.uuid4().hex[:16]}"
    isolated = None
    created = False
    try:
        _create_database(dbname, template=template_dbname)
        created = True
        isolated = Store(dsn=_store_database_dsn(dbname))
        _activate_cloned_seed_runtime(
            isolated, template_runtime_bundle, template_environment_seal)
        yield isolated
    finally:
        try:
            if isolated is not None:
                isolated.close()
        finally:
            if created:
                _drop_database(dbname)


@pytest.fixture
def fresh_pipeline(fresh_store):
    """Construct the governed pipeline only for tests that exercise it."""
    return GatePipeline(fresh_store)


@pytest.fixture
def fresh_outputs(fresh_store):
    """Construct governed outputs only for tests that exercise them."""
    return OutputGenerator(fresh_store)


@pytest.fixture
def fresh_env(fresh_store, fresh_pipeline, fresh_outputs):
    """Compatibility tuple for tests that exercise both governed services."""
    return fresh_store, fresh_pipeline, fresh_outputs


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
