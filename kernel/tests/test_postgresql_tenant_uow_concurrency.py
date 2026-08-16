"""Correlated PostgreSQL concurrency evidence for the tenant UnitOfWork."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from threading import Barrier, Event
from uuid import uuid4

import psycopg
import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient

from kernel.application_runtime import ApplicationRuntime, RuntimeMetadata
from kernel.runtime_config import RuntimeMode
from kernel.tenant_uow import (
    GovernedBatchRequest,
    TenantUnitOfWorkManager,
    create_tenant_connection_pool,
)
from kernel.tests.test_postgresql_tenant_migration import (
    ISSUER,
    CapabilityKeyAuthority,
    TenantAuthority,
    TenantTarget,
    authority,  # noqa: F401 - imported fixture
    capability_key,  # noqa: F401 - imported fixture
    tenant_target,  # noqa: F401 - imported fixture
)
from kernel.tests.test_postgresql_tenant_uow import (
    _FixtureMinter,
    _knowledge_head,
    _principal,
)
from kernel.tests import test_postgresql_tenant_uow as tenant_uow_support


@pytest.fixture(scope="module")
def target(request) -> TenantTarget:
    return request.getfixturevalue("tenant_target")


@pytest.fixture(scope="module")
def tenant_authority(request) -> TenantAuthority:
    return request.getfixturevalue("authority")


@pytest.fixture(scope="module")
def key_authority(request) -> CapabilityKeyAuthority:
    return request.getfixturevalue("capability_key")


@pytest.fixture(scope="module")
def other_authority(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
) -> TenantAuthority:
    fixture = tenant_uow_support.other_authority.__wrapped__
    return fixture(target, tenant_authority)


def _dedicated_manager(
    target: TenantTarget,
    key: CapabilityKeyAuthority,
    application_name: str,
    size: int,
) -> TenantUnitOfWorkManager:
    dsn = psycopg.conninfo.make_conninfo(
        target.role_dsn("ofarm_app"),
        application_name=application_name,
    )
    pool = create_tenant_connection_pool(dsn)
    manager = TenantUnitOfWorkManager(pool, _FixtureMinter(key))
    manager.initialize()
    try:
        pool.resize(size, size)
        pool.wait(timeout=5.0)
    except BaseException:
        manager.close()
        raise
    return manager


def test_same_tenant_allocation_blocks_until_prior_position_commits(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
    key_authority: CapabilityKeyAuthority,
) -> None:
    principal = _principal(target, tenant_authority)
    head_before = _knowledge_head(target, tenant_authority.tenant_id)
    first_ready = Event()
    second_attempting = Event()
    release_first = Event()
    waiter_application_name = f"uow-waiter-{uuid4().hex}"

    with ExitStack() as stack:
        first_manager = _dedicated_manager(
            target,
            key_authority,
            f"uow-holder-{uuid4().hex}",
            1,
        )
        stack.callback(first_manager.close)
        second_manager = _dedicated_manager(
            target,
            key_authority,
            waiter_application_name,
            1,
        )
        stack.callback(second_manager.close)

        def allocate_first() -> int:
            with first_manager.unit_of_work(principal) as unit:
                batch = unit.begin_batch(
                    GovernedBatchRequest(
                        f"batch-ordered-a-{uuid4().hex}",
                        "ORDERED_POSITION",
                        f"request-ordered-a-{uuid4().hex}",
                        tenant_authority.runtime_bundle_digest,
                    )
                )
                first_ready.set()
                if not release_first.wait(timeout=10):
                    raise TimeoutError("first allocator was not released")
                return batch.knowledge_position

        def allocate_second() -> int:
            if not first_ready.wait(timeout=10):
                raise TimeoutError("first allocator did not start")
            with second_manager.unit_of_work(principal) as unit:
                second_attempting.set()
                return unit.begin_batch(
                    GovernedBatchRequest(
                        f"batch-ordered-b-{uuid4().hex}",
                        "ORDERED_POSITION",
                        f"request-ordered-b-{uuid4().hex}",
                        tenant_authority.runtime_bundle_digest,
                    )
                ).knowledge_position

        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(allocate_first)
            second_future = executor.submit(allocate_second)
            blocked_backend = None
            try:
                assert first_ready.wait(timeout=10)
                assert second_attempting.wait(timeout=10)
                deadline = time.monotonic() + 5
                with psycopg.connect(target.target_admin_dsn) as admin:
                    while time.monotonic() < deadline:
                        blocked_backend = admin.execute(
                            """
                            SELECT pid, wait_event_type
                            FROM pg_catalog.pg_stat_activity
                            WHERE datname = pg_catalog.current_database()
                              AND usename = 'ofarm_app'
                              AND application_name = %s
                              AND wait_event_type = 'Lock'
                              AND query ~ (
                                  'INSERT[[:space:]]+INTO[[:space:]]+' ||
                                  'ofarm[.]governed_write_batch'
                              )
                            """,
                            (waiter_application_name,),
                        ).fetchone()
                        if blocked_backend is not None:
                            break
                        time.sleep(0.02)
            finally:
                release_first.set()
            first_position = first_future.result(timeout=10)
            second_position = second_future.result(timeout=10)

    assert blocked_backend is not None
    assert type(blocked_backend[0]) is int
    assert blocked_backend[1] == "Lock"
    assert first_position == head_before + 1
    assert second_position == head_before + 2


def test_asgi_concurrency_keeps_two_actors_on_two_backends(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
    other_authority: TenantAuthority,
    key_authority: CapabilityKeyAuthority,
) -> None:
    application_name = f"uow-asgi-{uuid4().hex}"
    manager = _dedicated_manager(target, key_authority, application_name, 2)
    principals = {
        "actor-a": _principal(target, tenant_authority),
        "actor-b": _principal(target, other_authority),
    }
    by_subject = {
        principal.identity.subject: principal for principal in principals.values()
    }

    class SecurityAudit:
        def authenticate(self, token):
            return by_subject[principals[token].identity.subject]

        def unit_of_work(self, principal):
            return manager.unit_of_work(principal)

    runtime = ApplicationRuntime(
        SecurityAudit(),
        object(),
        RuntimeMetadata(
            mode=RuntimeMode.PRODUCTION,
            deployment_image_digest="sha256:" + "1" * 64,
            oidc_issuer=ISSUER,
            oidc_audience="external-api",
            binder_audience="binder-audience",
            tenant_capability_kid="k" * 43,
        ),
        object(),
        object(),
        manager,
    )
    barrier = Barrier(3)
    release = Event()
    app = FastAPI()

    @app.get("/probe")
    def probe(authorization: str = Header()):
        principal = runtime.authenticate(authorization.removeprefix("Bearer "))
        with runtime.tenant_unit_of_work(principal) as unit:
            barrier.wait(timeout=10)
            if not release.wait(timeout=10):
                raise TimeoutError("ASGI backend evidence was not released")
            return {
                "tenant": str(unit.binding.tenant_id),
                "party": unit.binding.party_ref,
            }

    try:
        with (
            TestClient(app) as client,
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            futures = [
                executor.submit(
                    client.get,
                    "/probe",
                    headers={"Authorization": f"Bearer {actor}"},
                )
                for actor in principals
            ]
            try:
                barrier.wait(timeout=10)
                with psycopg.connect(target.target_admin_dsn) as admin:
                    backend_evidence = admin.execute(
                        """
                        SELECT pg_catalog.count(*),
                               pg_catalog.count(DISTINCT pid)
                        FROM pg_catalog.pg_stat_activity
                        WHERE datname = pg_catalog.current_database()
                          AND usename = 'ofarm_app'
                          AND application_name = %s
                          AND state = 'idle in transaction'
                        """,
                        (application_name,),
                    ).fetchone()
            finally:
                release.set()
            responses = [future.result(timeout=10) for future in futures]
    finally:
        manager.close()

    assert backend_evidence == (2, 2)
    assert {response.status_code for response in responses} == {200}
    bodies = [response.json() for response in responses]
    assert {body["tenant"] for body in bodies} == {
        str(tenant_authority.tenant_id),
        str(other_authority.tenant_id),
    }
    assert {body["party"] for body in bodies} == {
        tenant_authority.party_ref,
        other_authority.party_ref,
    }
