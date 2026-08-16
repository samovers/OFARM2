"""Real-role PostgreSQL tests for the tenant UnitOfWork."""
from __future__ import annotations

import time
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

from deployment.postgresql.tenant_contract import (
    OIDC_ISSUER_EQUALITY_POLICY,
    TENANT_CAPABILITY_CONTRACT,
    TenantCapability,
)
from kernel import tenant_uow as tenant_uow_module
from kernel.authentication import VerifiedIdentity
from kernel.principal_resolver import PrincipalBindingResolver
from kernel.tenant_uow import (
    GovernedBatchRequest,
    TenantUnitOfWorkManager,
    _reset_tenant_connection,
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
    _signed_capability_for_new_challenge,
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


def _knowledge_head(target: TenantTarget, tenant_id) -> int:
    with psycopg.connect(target.target_admin_dsn) as admin:
        value = admin.execute(
            """
            SELECT COALESCE(pg_catalog.max(knowledge_position), 0)
            FROM ofarm.governed_write_batch
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        ).fetchone()[0]
    assert type(value) is int
    return value


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
                governed_operation, request_id, runtime_bundle_digest,
                knowledge_position
            ) VALUES (%s, %s, %s, %s, %s, %s, 1)
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


def test_real_pool_binds_allocates_and_rolls_back_atomically(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
    tenant_manager: TenantUnitOfWorkManager,
) -> None:
    principal = _principal(target, tenant_authority)
    head_before = _knowledge_head(target, tenant_authority.tenant_id)
    committed_batch = f"batch-uow-{uuid4().hex}"
    committed_request = f"request-uow-{uuid4().hex}"

    with tenant_manager.unit_of_work(principal) as unit:
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
        assert batch.knowledge_position == head_before + 1

    rolled_back_batch = f"batch-uow-{uuid4().hex}"
    rolled_back_position: list[int] = []
    with pytest.raises(RuntimeError, match="force rollback"):
        with tenant_manager.unit_of_work(principal) as unit:
            assert unit.binding.capability_nonce != first_nonce
            rolled_back = unit.begin_batch(
                GovernedBatchRequest(
                    rolled_back_batch,
                    "UOW_REFUSE",
                    f"request-uow-{uuid4().hex}",
                    tenant_authority.runtime_bundle_digest,
                )
            )
            rolled_back_position.append(rolled_back.knowledge_position)
            raise RuntimeError("force rollback")

    replacement_batch = f"batch-uow-{uuid4().hex}"
    with tenant_manager.unit_of_work(principal) as unit:
        replacement = unit.begin_batch(
            GovernedBatchRequest(
                replacement_batch,
                "UOW_RETRY",
                f"request-uow-{uuid4().hex}",
                tenant_authority.runtime_bundle_digest,
            )
        )
    assert replacement.knowledge_position == rolled_back_position[0]

    with psycopg.connect(target.target_admin_dsn) as admin:
        rows = admin.execute(
            """
            SELECT batch_id, knowledge_position
            FROM ofarm.governed_write_batch
            WHERE tenant_id = %s AND batch_id = ANY(%s)
            ORDER BY knowledge_position
            """,
            (
                tenant_authority.tenant_id,
                [committed_batch, rolled_back_batch, replacement_batch],
            ),
        ).fetchall()
    assert rows == [
        (committed_batch, head_before + 1),
        (replacement_batch, head_before + 2),
    ]


def test_empty_unit_of_work_consumes_no_knowledge_position(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
    tenant_manager: TenantUnitOfWorkManager,
) -> None:
    principal = _principal(target, tenant_authority)
    head_before = _knowledge_head(target, tenant_authority.tenant_id)

    with tenant_manager.unit_of_work(principal) as unit:
        assert unit.batch is None

    assert _knowledge_head(target, tenant_authority.tenant_id) == head_before


def test_hostile_sql_has_no_unit_of_work_ingress_and_batch_rolls_back(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
    tenant_manager: TenantUnitOfWorkManager,
) -> None:
    principal = _principal(target, tenant_authority)
    batch_id = f"batch-hostile-{uuid4().hex}"
    hostile_sql = (
        "/* repository operation */ COMMIT",
        "-- repository operation\nROLLBACK",
        "PREPARE TRANSACTION 'uow_escape'",
        "SET SESSION statement_timeout = 0",
        "SELECT pg_advisory_lock(42)",
    )
    sql_method_name = "execute"

    with pytest.raises(RuntimeError, match="later governed stage refused"):
        with tenant_manager.unit_of_work(principal) as unit:
            unit.begin_batch(
                GovernedBatchRequest(
                    batch_id,
                    "HOSTILE_SQL_REFUSAL",
                    f"request-hostile-{uuid4().hex}",
                    tenant_authority.runtime_bundle_digest,
                )
            )
            for query in hostile_sql:
                with pytest.raises(AttributeError):
                    getattr(unit, sql_method_name)(query)
            raise RuntimeError("later governed stage refused")

    with psycopg.connect(target.target_admin_dsn) as admin:
        assert admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm.governed_write_batch
            WHERE tenant_id = %s AND batch_id = %s
            """,
            (tenant_authority.tenant_id, batch_id),
        ).fetchone() == (0,)
        assert admin.execute("SHOW max_prepared_transactions").fetchone() == ("0",)


def test_pool_reset_cleans_session_before_same_backend_serves_second_tenant(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
    other_authority: TenantAuthority,
    key_authority: CapabilityKeyAuthority,
) -> None:
    pool = create_tenant_connection_pool(target.role_dsn("ofarm_app"))
    manager = TenantUnitOfWorkManager(pool, _FixtureMinter(key_authority))
    statement_name = f"uow_reset_{uuid4().hex}"
    channel_name = f"uow_reset_{uuid4().hex}"
    manager.initialize()
    # Fixed size makes backend reuse evidence independent of elastic growth.
    pool.resize(1, 1)
    try:
        with pool.connection(timeout=5.0) as connection:
            backend_pid = connection.execute(
                "SELECT pg_catalog.pg_backend_pid()"
            ).fetchone()[0]
            baseline_timeout = connection.execute(
                "SHOW statement_timeout"
            ).fetchone()[0]
            assert connection.prepare_threshold is None
            connection.execute("SET SESSION statement_timeout = 0")
            connection.execute(
                f"PREPARE {statement_name} AS SELECT 1",
                prepare=False,
            )
            connection.execute(f"LISTEN {channel_name}", prepare=False)

        with manager.unit_of_work(
            _principal(target, tenant_authority)
        ) as first_unit:
            assert first_unit.binding.tenant_id == tenant_authority.tenant_id
        with manager.unit_of_work(
            _principal(target, other_authority)
        ) as second_unit:
            assert second_unit.binding.tenant_id == other_authority.tenant_id

        with pool.connection(timeout=5.0) as connection:
            assert connection.execute(
                "SELECT pg_catalog.pg_backend_pid()"
            ).fetchone() == (backend_pid,)
            assert connection.execute(
                "SHOW statement_timeout"
            ).fetchone() == (baseline_timeout,)
            assert connection.execute(
                """
                SELECT pg_catalog.count(*)
                FROM pg_catalog.pg_prepared_statements
                WHERE name = %s
                """,
                (statement_name,),
            ).fetchone() == (0,)
            channels = connection.execute(
                """
                SELECT channel
                FROM pg_catalog.pg_listening_channels() AS channels(channel)
                """
            ).fetchall()
            assert (channel_name,) not in channels
    finally:
        manager.close()


def test_reset_callback_clears_temporary_objects_and_session_advisory_locks(
    target: TenantTarget,
) -> None:
    temporary_table = f"uow_reset_{uuid4().hex}"
    lock_key = uuid4().int % 2_147_483_647

    with psycopg.connect(target.target_admin_dsn) as connection:
        connection.execute(
            f"CREATE TEMPORARY TABLE {temporary_table} (value integer)",
            prepare=False,
        )
        connection.execute(
            "SELECT pg_catalog.pg_advisory_lock(%s)",
            (lock_key,),
        )
        connection.commit()

        _reset_tenant_connection(connection)

        assert connection.execute(
            "SELECT pg_catalog.to_regclass(%s)",
            (f"pg_temp.{temporary_table}",),
        ).fetchone() == (None,)
        assert connection.execute(
            """
            SELECT pg_catalog.count(*)
            FROM pg_catalog.pg_locks
            WHERE pid = pg_catalog.pg_backend_pid()
              AND locktype = 'advisory'
            """
        ).fetchone() == (0,)


def test_pool_discards_backend_when_reset_callback_refuses(
    target: TenantTarget,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse_reset(_connection) -> None:
        raise RuntimeError("forced tenant reset refusal")

    monkeypatch.setattr(
        tenant_uow_module,
        "_reset_tenant_connection",
        refuse_reset,
    )
    pool = create_tenant_connection_pool(target.role_dsn("ofarm_app"))
    pool.open(wait=True, timeout=5.0)
    # The next checkout can only follow reset/discard, not normal pool growth.
    pool.resize(1, 1)
    try:
        with pool.connection(timeout=5.0) as first_connection:
            first_pid = first_connection.execute(
                "SELECT pg_catalog.pg_backend_pid()"
            ).fetchone()[0]

        with pool.connection(timeout=5.0) as replacement_connection:
            replacement_pid = replacement_connection.execute(
                "SELECT pg_catalog.pg_backend_pid()"
            ).fetchone()[0]

        assert first_connection.closed
        assert replacement_pid != first_pid
    finally:
        pool.close(timeout=5.0)


def test_governed_batch_request_has_no_knowledge_position_input(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
    tenant_manager: TenantUnitOfWorkManager,
) -> None:
    principal = _principal(target, tenant_authority)
    head_before = _knowledge_head(target, tenant_authority.tenant_id)

    with tenant_manager.unit_of_work(principal) as unit:
        with pytest.raises(TypeError, match="knowledge_position"):
            GovernedBatchRequest(
                batch_id=f"batch-explicit-{uuid4().hex}",
                operation="EXPLICIT_POSITION",
                request_id=f"request-explicit-{uuid4().hex}",
                runtime_bundle_digest=tenant_authority.runtime_bundle_digest,
                knowledge_position=head_before + 1,
            )
        accepted = unit.begin_batch(
            GovernedBatchRequest(
                f"batch-allocated-{uuid4().hex}",
                "DATABASE_POSITION",
                f"request-allocated-{uuid4().hex}",
                tenant_authority.runtime_bundle_digest,
            )
        )

    assert accepted.knowledge_position == head_before + 1


def test_runtime_database_refuses_explicit_knowledge_position(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
    key_authority: CapabilityKeyAuthority,
) -> None:
    head_before = _knowledge_head(target, tenant_authority.tenant_id)
    batch_id = f"batch-explicit-{uuid4().hex}"

    with psycopg.connect(target.role_dsn("ofarm_app")) as application:
        application.execute("BEGIN ISOLATION LEVEL READ COMMITTED")
        capability = _signed_capability_for_new_challenge(
            application,
            authority=tenant_authority,
            key=key_authority,
        )
        application.execute(
            "SELECT ofarm.bind_tenant_capability(%s)",
            (capability,),
        )
        context = application.execute(
            "SELECT * FROM ofarm.current_tenant_context()"
        ).fetchone()
        assert context is not None
        assert context[7] == tenant_authority.tenant_id

        with pytest.raises(
            psycopg.errors.InvalidParameterValue,
            match="runtime knowledge position is database assigned",
        ):
            application.execute(
                """
                INSERT INTO ofarm.governed_write_batch (
                    tenant_id, batch_id, authenticated_principal_ref,
                    governed_operation, request_id, runtime_bundle_digest,
                    knowledge_position
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    tenant_authority.tenant_id,
                    batch_id,
                    tenant_authority.party_ref,
                    "EXPLICIT_POSITION",
                    f"request-explicit-{uuid4().hex}",
                    tenant_authority.runtime_bundle_digest,
                    head_before + 1,
                ),
            )
        application.rollback()

    with psycopg.connect(target.target_admin_dsn) as admin:
        assert admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm.governed_write_batch
            WHERE tenant_id = %s AND batch_id = %s
            """,
            (tenant_authority.tenant_id, batch_id),
        ).fetchone() == (0,)
    assert _knowledge_head(target, tenant_authority.tenant_id) == head_before


def test_knowledge_positions_are_tenant_local(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
    other_authority: TenantAuthority,
    tenant_manager: TenantUnitOfWorkManager,
) -> None:
    first_head = _knowledge_head(target, tenant_authority.tenant_id)
    other_head = _knowledge_head(target, other_authority.tenant_id)

    with tenant_manager.unit_of_work(
        _principal(target, tenant_authority)
    ) as first_unit:
        first = first_unit.begin_batch(
            GovernedBatchRequest(
                f"batch-local-a-{uuid4().hex}",
                "TENANT_LOCAL",
                f"request-local-a-{uuid4().hex}",
                tenant_authority.runtime_bundle_digest,
            )
        )
    with tenant_manager.unit_of_work(
        _principal(target, other_authority)
    ) as other_unit:
        other = other_unit.begin_batch(
            GovernedBatchRequest(
                f"batch-local-b-{uuid4().hex}",
                "TENANT_LOCAL",
                f"request-local-b-{uuid4().hex}",
                other_authority.runtime_bundle_digest,
            )
        )

    assert first.knowledge_position == first_head + 1
    assert other.knowledge_position == other_head + 1
    with psycopg.connect(target.target_admin_dsn) as admin:
        assert admin.execute(
            """
            SELECT pg_catalog.count(DISTINCT tenant_id)
            FROM ofarm.governed_write_batch
            WHERE knowledge_position = 1
            """
        ).fetchone() == (2,)
