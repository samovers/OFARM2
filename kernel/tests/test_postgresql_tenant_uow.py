"""Real-role PostgreSQL and ASGI tests for the tenant UnitOfWork."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from deployment.postgresql.tenant_contract import (
    OIDC_ISSUER_EQUALITY_POLICY,
    TENANT_CAPABILITY_CONTRACT,
    TenantCapability,
)
from kernel.authentication import VerifiedIdentity
from kernel.application_runtime import ApplicationRuntime, RuntimeMetadata
from kernel.principal_resolver import PrincipalBindingResolver
from kernel.runtime_config import RuntimeMode
from kernel.tenant_uow import (
    GovernedBatchRequest,
    TenantUnitOfWorkManager,
    create_tenant_connection_pool,
)
from kernel.tests.tenant_capability_fixture import sign_capability
from kernel.tests.test_postgresql_tenant_migration import (
    ISSUER,
    PARTY_KIND,
    CapabilityKeyAuthority,
    TenantAuthority,
    TenantTarget,
    _canonical_json,
    _compute_act_digest,
    _compute_binding_digest,
    _sha256_id,
    _transition,
    authority,  # noqa: F401 - imported fixture
    capability_key,  # noqa: F401 - imported fixture
    tenant_target,  # noqa: F401 - imported fixture
)


def _raw_digest(value: str) -> bytes:
    return bytes.fromhex(value.removeprefix("sha256:"))


class _FixtureMinter:
    def __init__(self, key: CapabilityKeyAuthority) -> None:
        self._key = key

    def mint(self, identity, principal_authority, challenge):
        now_us = time.time_ns() // 1_000
        capability = TenantCapability(
            contract_digest=TENANT_CAPABILITY_CONTRACT.raw_digest,
            challenge_id=challenge.challenge_id,
            audience=challenge.audience,
            key_id=self._key.kid,
            equality_policy=identity.equality_policy,
            issuer=identity.issuer,
            subject=identity.subject,
            binding_version_id=principal_authority.binding_version_id,
            binding_version_digest=_raw_digest(
                principal_authority.binding_version_digest
            ),
            lifecycle_head_id=principal_authority.lifecycle_head_id,
            lifecycle_head_digest=_raw_digest(
                principal_authority.lifecycle_head_digest
            ),
            tenant_id=principal_authority.tenant_id,
            tenant_registration_digest=_raw_digest(
                principal_authority.tenant_registration_digest
            ),
            party_ref=principal_authority.party_ref,
            party_record_kind=principal_authority.party_record_kind,
            party_record_id=principal_authority.party_record_id,
            party_schema_digest=_raw_digest(
                principal_authority.party_schema_digest
            ),
            party_payload_digest=_raw_digest(
                principal_authority.party_payload_digest
            ),
            issued_at_unix_microseconds=now_us,
            not_before_unix_microseconds=now_us,
            expires_at_unix_microseconds=now_us + 30_000_000,
            nonce=uuid4(),
        )
        return sign_capability(capability)


def _principal(target: TenantTarget, tenant_authority: TenantAuthority):
    app_dsn = target.role_dsn("ofarm_app")
    resolver = PrincipalBindingResolver(lambda: psycopg.connect(app_dsn))
    resolver.initialize()
    return resolver.resolve(
        VerifiedIdentity(
            equality_policy=OIDC_ISSUER_EQUALITY_POLICY,
            issuer=ISSUER,
            subject=tenant_authority.subject,
        )
    )


@pytest.fixture(scope="module")
def target(request) -> TenantTarget:
    return request.getfixturevalue("tenant_target")


@pytest.fixture(scope="module")
def tenant_authority(request) -> TenantAuthority:
    return request.getfixturevalue("authority")


@pytest.fixture(scope="module")
def key_authority(request) -> CapabilityKeyAuthority:
    return request.getfixturevalue("capability_key")


@pytest.fixture
def tenant_manager(
    target: TenantTarget,
    key_authority: CapabilityKeyAuthority,
):
    manager = TenantUnitOfWorkManager(
        create_tenant_connection_pool(target.role_dsn("ofarm_app")),
        _FixtureMinter(key_authority),
    )
    manager.initialize()
    yield manager
    manager.close()


@pytest.fixture(scope="module")
def other_authority(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
) -> TenantAuthority:
    subject = "subject-tenant-02"
    party_ref = "party-02"
    batch_id = f"batch-authority-{uuid4().hex}"
    payload = {"partyId": party_ref, "partyState": "ACTIVE"}
    payload_digest = _sha256_id(_canonical_json(payload))
    with psycopg.connect(target.target_admin_dsn) as admin:
        document = admin.execute(
            """
            SELECT pg_catalog.convert_from(canonical_bytes, 'UTF8')::jsonb
            FROM ofarm.runtime_bundle
            WHERE tenant_id = %s AND bundle_digest = %s
            """,
            (
                tenant_authority.tenant_id,
                tenant_authority.runtime_bundle_digest,
            ),
        ).fetchone()[0]
        assert admin.execute(
            "SELECT ofarm.publish_runtime_bundle(%s, %s, %s)",
            (
                tenant_authority.other_tenant_id,
                tenant_authority.runtime_bundle_digest,
                Jsonb(document),
            ),
        ).fetchone() == (tenant_authority.runtime_bundle_digest,)
        admin.execute(
            """
            INSERT INTO ofarm.governed_write_batch (
                tenant_id, batch_id, authenticated_principal_ref,
                governed_operation, request_id, runtime_bundle_digest
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                tenant_authority.other_tenant_id,
                batch_id,
                party_ref,
                "AUTHORITY_BOOTSTRAP",
                f"request-authority-{uuid4().hex}",
                tenant_authority.runtime_bundle_digest,
            ),
        )
        admin.execute(
            """
            INSERT INTO ofarm.kernel_record (
                tenant_id, record_id, record_kind, lane, schema_digest,
                payload, payload_digest, batch_id, runtime_bundle_digest
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                tenant_authority.other_tenant_id,
                party_ref,
                PARTY_KIND,
                "canonical",
                tenant_authority.party_schema_digest,
                Jsonb(payload),
                payload_digest,
                batch_id,
                tenant_authority.runtime_bundle_digest,
            ),
        )

    version_id = uuid4()
    head_id = uuid4()
    with psycopg.connect(
        target.role_dsn("ofarm_identity_control_login")
    ) as identity:
        valid_from, valid_until, effective_at, decided_at = identity.execute(
            """
            SELECT pg_catalog.clock_timestamp() - INTERVAL '1 day',
                   pg_catalog.clock_timestamp() + INTERVAL '1 day',
                   pg_catalog.clock_timestamp() - INTERVAL '2 seconds',
                   pg_catalog.clock_timestamp() - INTERVAL '1 second'
            """
        ).fetchone()
        version_digest = _compute_binding_digest(
            identity,
            subject=subject,
            binding_version_id=version_id,
            authority=None,
            tenant_id=tenant_authority.other_tenant_id,
            tenant_registration_digest=(
                tenant_authority.other_tenant_registration_digest
            ),
            party_ref=party_ref,
            party_schema_digest=tenant_authority.party_schema_digest,
            party_payload_digest=payload_digest,
            valid_from=valid_from,
            valid_until=valid_until,
        )
        head_digest = _compute_act_digest(
            identity,
            subject=subject,
            stream_sequence=1,
            act_id=head_id,
            act_kind="ACTIVATE",
            binding_version_id=version_id,
            binding_version_digest=version_digest,
            prior_act_id=None,
            prior_act_digest=None,
            successor_version_id=None,
            successor_version_digest=None,
            effective_at=effective_at,
            decided_at=decided_at,
            reason="second-actor-activation",
        )
        _transition(
            identity,
            subject=subject,
            expected_head_id=None,
            expected_head_digest=None,
            act_id=head_id,
            act_digest=head_digest,
            act_kind="ACTIVATE",
            binding_version_id=version_id,
            binding_version_digest=version_digest,
            candidate_version_id=version_id,
            candidate_version_digest=version_digest,
            tenant_id=tenant_authority.other_tenant_id,
            tenant_registration_digest=(
                tenant_authority.other_tenant_registration_digest
            ),
            party_ref=party_ref,
            party_schema_digest=tenant_authority.party_schema_digest,
            party_payload_digest=payload_digest,
            valid_from=valid_from,
            valid_until=valid_until,
            predecessor_version_id=None,
            effective_at=effective_at,
            decided_at=decided_at,
            reason="second-actor-activation",
        )
    return TenantAuthority(
        target_admin_dsn=target.target_admin_dsn,
        tenant_id=tenant_authority.other_tenant_id,
        tenant_registration_digest=(
            tenant_authority.other_tenant_registration_digest
        ),
        subject=subject,
        party_ref=party_ref,
        other_tenant_id=tenant_authority.tenant_id,
        other_tenant_registration_digest=(
            tenant_authority.tenant_registration_digest
        ),
        party_schema_digest=tenant_authority.party_schema_digest,
        party_payload_digest=payload_digest,
        binding_version_id=version_id,
        binding_version_digest=version_digest,
        lifecycle_head_id=head_id,
        lifecycle_head_digest=head_digest,
        runtime_bundle_digest=tenant_authority.runtime_bundle_digest,
        batch_id=batch_id,
    )


def test_real_pool_binds_allocates_rolls_back_and_reuses_idle_backend(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
    tenant_manager: TenantUnitOfWorkManager,
) -> None:
    principal = _principal(target, tenant_authority)
    committed_batch = f"batch-uow-{uuid4().hex}"
    committed_request = f"request-uow-{uuid4().hex}"

    with tenant_manager.unit_of_work(principal) as unit:
        first_pid = unit.fetch_one("SELECT pg_catalog.pg_backend_pid()")[0]
        first_nonce = unit.binding.capability_nonce
        assert unit.binding.tenant_id == tenant_authority.tenant_id
        assert unit.binding.party_record_kind == PARTY_KIND
        batch = unit.begin_batch(
            GovernedBatchRequest(
                committed_batch,
                "UOW_ACCEPT",
                committed_request,
                tenant_authority.runtime_bundle_digest,
            )
        )
        assert batch.tenant_id == tenant_authority.tenant_id
        assert unit.fetch_one("SELECT ofarm.current_tenant_id()") == (
            tenant_authority.tenant_id,
        )

    rolled_back_batch = f"batch-uow-{uuid4().hex}"
    with pytest.raises(RuntimeError, match="force rollback"):
        with tenant_manager.unit_of_work(principal) as unit:
            second_pid = unit.fetch_one("SELECT pg_catalog.pg_backend_pid()")[0]
            assert second_pid == first_pid
            assert unit.binding.capability_nonce != first_nonce
            unit.begin_batch(
                GovernedBatchRequest(
                    rolled_back_batch,
                    "UOW_REFUSE",
                    f"request-uow-{uuid4().hex}",
                    tenant_authority.runtime_bundle_digest,
                )
            )
            raise RuntimeError("force rollback")

    with psycopg.connect(target.target_admin_dsn) as admin:
        rows = admin.execute(
            """
            SELECT batch_id
            FROM ofarm.governed_write_batch
            WHERE tenant_id = %s AND batch_id = ANY(%s)
            ORDER BY batch_id
            """,
            (tenant_authority.tenant_id, [committed_batch, rolled_back_batch]),
        ).fetchall()
    assert rows == [(committed_batch,)]


def test_asgi_concurrency_keeps_two_actors_in_two_tenants(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
    other_authority: TenantAuthority,
    tenant_manager: TenantUnitOfWorkManager,
) -> None:
    principals = {
        "actor-a": _principal(target, tenant_authority),
        "actor-b": _principal(target, other_authority),
    }
    by_subject = {
        principal.identity.subject: principal
        for principal in principals.values()
    }

    class Verifier:
        def verify(self, token):
            return principals[token].identity

    class Resolver:
        def resolve(self, identity):
            return by_subject[identity.subject]

    runtime = ApplicationRuntime(
        Verifier(),
        Resolver(),
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
        tenant_manager,
    )
    barrier = Barrier(2)
    app = FastAPI()

    @app.get("/probe")
    def probe(authorization: str = Header()):
        principal = runtime.authenticate(
            authorization.removeprefix("Bearer ")
        )
        with runtime.tenant_unit_of_work(principal) as unit:
            barrier.wait(timeout=5)
            return {
                "tenant": str(unit.binding.tenant_id),
                "party": unit.binding.party_ref,
                "backend": unit.fetch_one(
                    "SELECT pg_catalog.pg_backend_pid()"
                )[0],
            }

    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                client.get,
                "/probe",
                headers={"Authorization": f"Bearer {actor}"},
            )
            for actor in principals
        ]
        responses = [future.result(timeout=10) for future in futures]

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
    assert len({body["backend"] for body in bodies}) == 2
