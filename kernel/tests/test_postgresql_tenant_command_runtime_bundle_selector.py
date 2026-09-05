"""Real PostgreSQL evidence for the fixed tenant RuntimeBundle selector."""
from __future__ import annotations

import inspect
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import psycopg
import pytest

from deployment.postgresql import tenant_command_runtime_bundle_selection as control
from deployment.postgresql.audit_contract import SECURITY_AUDIT_CONTRACT
from kernel.application_runtime import ApplicationRuntime
from kernel.request_router_audit import RequestRouterAuditProducer
from kernel.security_audit import CorrelationHmac
from kernel.security_audit_client import PreTenantAuditClient
from kernel.security_audit_health import SecurityAuditHealth
from kernel.security_audit_runtime import (
    PreTenantAuditRuntime,
    _audit_producer_connection_factory,
    _live_gap_controller,
    _producer,
)
from kernel.tenant_command_runtime_bundle_selector import (
    CommandRuntimeBundleSelectionRefused,
    _fixed_binding,
    _load_bundle,
    _resolve_commit_operation_claim_draft_runtime_bundle,
    _selection_authority,
    _validate_closure,
)
from kernel.tenant_uow import (
    GovernedBatchRequest,
    TenantUnitOfWorkManager,
    create_tenant_connection_pool,
)
from kernel.tests.postgresql_audit_support import audit_service_fixture  # noqa: F401
from kernel.tests.postgresql_audit_support import role_dsn
from kernel.tests.test_postgresql_tenant_migration import (
    CapabilityKeyAuthority,
    TenantAuthority,
    TenantTarget,
    _extended_command_selection_bundle,
    _insert_batch,
    _install_test_bound_context,
    _publish_model_runtime_bundle,
    authority,  # noqa: F401 - imported fixture
    capability_key,  # noqa: F401 - imported fixture
    command_selection_bundle,  # noqa: F401 - imported fixture
    other_authority,  # noqa: F401 - imported fixture
    tenant_target,  # noqa: F401 - imported fixture
)
from kernel.tests.test_postgresql_tenant_uow import _FixtureMinter, _principal


_RESOLVER = (
    "ofarm.resolve_commit_operation_claim_draft_"
    "runtime_bundle_selection()"
)


class _FixedCorrelationHmac:
    def create(self) -> CorrelationHmac:
        version = SECURITY_AUDIT_CONTRACT.correlation_hmac.key_version
        assert version is not None
        return CorrelationHmac(b"r" * 32, version)


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
def other_tenant_authority(request) -> TenantAuthority:
    return request.getfixturevalue("other_authority")


@pytest.fixture(scope="module")
def selected_bundle(request):
    return request.getfixturevalue("command_selection_bundle")


@pytest.fixture(scope="module")
def active_selection(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
    selected_bundle,
):
    with psycopg.connect(
        target.role_dsn(
            "ofarm_command_runtime_bundle_selection_control_login"
        )
    ) as connection:
        _install_test_bound_context(connection, tenant_authority)
        return control.activate_commit_operation_claim_draft_runtime_bundle_selection(
            connection,
            selected_bundle,
        )


@pytest.fixture
def manager(
    target: TenantTarget,
    key_authority: CapabilityKeyAuthority,
):
    value = TenantUnitOfWorkManager(
        create_tenant_connection_pool(target.role_dsn("ofarm_app")),
        _FixtureMinter(key_authority),
    )
    value.initialize()
    yield value
    value.close()


def _tenant_state(
    target: TenantTarget,
    tenant_id: UUID,
    audit_state: dict[str, object],
) -> tuple[object, ...]:
    with psycopg.connect(target.target_admin_dsn) as connection:
        tenant = connection.execute(
            """
            SELECT
                (SELECT count(*)
                   FROM ofarm.tenant_command_runtime_bundle_selection
                  WHERE tenant_id = %s),
                (SELECT count(*) FROM ofarm.governed_write_batch
                  WHERE tenant_id = %s),
                (SELECT max(knowledge_position)
                   FROM ofarm.governed_write_batch WHERE tenant_id = %s)
            """,
            (tenant_id, tenant_id, tenant_id),
        ).fetchone()
    with psycopg.connect(str(audit_state["target_admin_dsn"])) as connection:
        audit = connection.execute(
            "SELECT count(*) FROM ofarm_security.operational_security_event"
        ).fetchone()
    assert tenant is not None and audit is not None
    return (*tenant, audit[0])


def _runtime(
    manager: TenantUnitOfWorkManager,
    audit_state: dict[str, object],
    monkeypatch,
) -> tuple[ApplicationRuntime, list[tuple[object, object]], object]:
    observed = []
    original = RequestRouterAuditProducer.unit_of_work

    def observe(request_router, principal):
        observed.append((request_router, principal))
        return original(request_router, principal)

    monkeypatch.setattr(RequestRouterAuditProducer, "unit_of_work", observe)
    health = SecurityAuditHealth()
    request_router_client = PreTenantAuditClient(
        _audit_producer_connection_factory(
            role_dsn(audit_state, "ofarm_security_request_router_producer_login")
        ),
        _producer("REQUEST_ROUTER"),
    )
    request_router = RequestRouterAuditProducer(
        manager,
        _live_gap_controller(
            role_dsn(audit_state, "ofarm_security_audit_control_login")
        ).request_router_sink(
            health.request_router_sink(
                _FixedCorrelationHmac(),
                request_router_client,
            )
        ),
    )
    runtime = ApplicationRuntime(
        PreTenantAuditRuntime(
            object(),  # type: ignore[arg-type]
            request_router,
            health,
        ),
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        manager,
    )
    return runtime, observed, request_router


def _set_app_resolver_execute(target: TenantTarget, *, granted: bool) -> None:
    action = "GRANT" if granted else "REVOKE"
    direction = "TO" if granted else "FROM"
    with psycopg.connect(target.target_admin_dsn) as connection:
        connection.execute("SET ROLE ofarm_owner")
        connection.execute(
            f"{action} EXECUTE ON FUNCTION {_RESOLVER} {direction} ofarm_app"
        )


def test_application_runtime_resolves_exact_bundle_once_without_a_write(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
    key_authority: CapabilityKeyAuthority,
    selected_bundle,
    active_selection,
    manager: TenantUnitOfWorkManager,
    migrated_audit_service,
    monkeypatch,
) -> None:
    del key_authority
    before = _tenant_state(
        target,
        tenant_authority.tenant_id,
        migrated_audit_service,
    )
    principal = _principal(target, tenant_authority)
    with psycopg.connect(target.role_dsn("ofarm_app")) as connection:
        _install_test_bound_context(connection, tenant_authority)
        authority_row = _selection_authority(
            connection,
            tenant_authority.tenant_id,
        )
        loaded = _load_bundle(
            connection,
            tenant_authority.tenant_id,
            authority_row[9],
        )
        _validate_closure(_fixed_binding(), loaded)

    runtime, observed, request_router = _runtime(
        manager,
        migrated_audit_service,
        monkeypatch,
    )
    with runtime.tenant_unit_of_work(principal) as unit:
        resolved = (
            unit.resolve_commit_operation_claim_draft_runtime_bundle()
        )
        again = unit.resolve_commit_operation_claim_draft_runtime_bundle()
        assert again is resolved
        assert resolved.tenant_id == tenant_authority.tenant_id
        assert resolved.selection_batch_id == active_selection.selection_batch_id
        assert (
            resolved.selection_knowledge_position
            == active_selection.selection_knowledge_position
        )
        assert resolved.selection_knowledge_cut == before[2]
        assert resolved.runtime_bundle == selected_bundle
        assert resolved.runtime_bundle_digest == selected_bundle.digest
        assert (
            resolved.runtime_bundle_document
            == selected_bundle.canonical_document_bytes
        )
        assert tuple(
            component.canonical_bytes
            for component in resolved.runtime_bundle.components
        ) == tuple(
            component.canonical_bytes for component in selected_bundle.components
        )

    assert observed == [(request_router, principal)]
    assert _tenant_state(
        target,
        tenant_authority.tenant_id,
        migrated_audit_service,
    ) == before
    with pytest.raises(RuntimeError, match="closed"):
        unit.resolve_commit_operation_claim_draft_runtime_bundle()


@pytest.mark.parametrize("role", ("ofarm_app", "ofarm_worker"))
def test_bound_runtime_roles_can_call_only_the_fixed_zero_argument_read(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
    active_selection,
    role: str,
) -> None:
    del active_selection
    with psycopg.connect(target.role_dsn(role)) as connection:
        _install_test_bound_context(connection, tenant_authority)
        row = connection.execute(f"SELECT * FROM {_RESOLVER}").fetchone()
        resolved = _resolve_commit_operation_claim_draft_runtime_bundle(
            connection,
            tenant_authority.tenant_id,
        )

    assert row[0] == tenant_authority.tenant_id
    assert row[9] == resolved.runtime_bundle_digest
    assert row[10] == resolved.selection_knowledge_cut
    assert tuple(inspect.signature(
        type(resolved).__init__
    ).parameters) == ("self", "args", "kwargs")


def test_unbound_and_non_runtime_sessions_cannot_execute_the_resolver(
    target: TenantTarget,
) -> None:
    for role in ("ofarm_app", "ofarm_worker"):
        with psycopg.connect(target.role_dsn(role)) as connection:
            with pytest.raises(psycopg.Error):
                connection.execute(f"SELECT * FROM {_RESOLVER}").fetchall()
    for role in (
        "ofarm_readiness",
        "ofarm_runtime_bundle_control_login",
        "ofarm_tenant_control_login",
        "ofarm_identity_control_login",
        "ofarm_command_runtime_bundle_selection_control_login",
    ):
        with psycopg.connect(target.role_dsn(role)) as connection:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                connection.execute(f"SELECT * FROM {_RESOLVER}").fetchall()


def test_runtime_roles_have_no_direct_selection_table_authority(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
) -> None:
    statements = (
        "SELECT * FROM ofarm.tenant_command_runtime_bundle_selection",
        "DELETE FROM ofarm.tenant_command_runtime_bundle_selection",
        "UPDATE ofarm.tenant_command_runtime_bundle_selection "
        "SET selection_batch_id = selection_batch_id",
    )
    for role in ("ofarm_app", "ofarm_worker"):
        for statement in statements:
            with psycopg.connect(target.role_dsn(role)) as connection:
                _install_test_bound_context(connection, tenant_authority)
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    connection.execute(statement).fetchall()


def test_catalog_closes_resolver_policy_and_acl_shape(
    target: TenantTarget,
) -> None:
    with psycopg.connect(target.target_admin_dsn) as connection:
        routine = connection.execute(
            """
            SELECT owner.rolname::text, language.lanname::text,
                   routine.prosecdef, routine.provolatile,
                   routine.proparallel, routine.proconfig,
                   pg_catalog.pg_get_function_result(routine.oid),
                   pg_catalog.pg_get_function_identity_arguments(routine.oid)
              FROM pg_catalog.pg_proc AS routine
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = routine.pronamespace
              JOIN pg_catalog.pg_roles AS owner
                ON owner.oid = routine.proowner
              JOIN pg_catalog.pg_language AS language
                ON language.oid = routine.prolang
             WHERE namespace.nspname = 'ofarm'
               AND routine.proname =
                   'resolve_commit_operation_claim_draft_runtime_bundle_selection'
            """
        ).fetchone()
        acl = connection.execute(
            """
            SELECT CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                        ELSE pg_catalog.pg_get_userbyid(acl.grantee) END,
                   acl.privilege_type, acl.is_grantable
              FROM pg_catalog.pg_proc AS routine
              JOIN pg_catalog.pg_namespace AS namespace
                ON namespace.oid = routine.pronamespace
              CROSS JOIN LATERAL pg_catalog.aclexplode(routine.proacl) AS acl
             WHERE namespace.nspname = 'ofarm'
               AND routine.proname =
                   'resolve_commit_operation_claim_draft_runtime_bundle_selection'
             ORDER BY 1, 2, 3
            """
        ).fetchall()
        policies = connection.execute(
            """
            SELECT tablename, policyname, permissive, roles, cmd,
                   qual, with_check
              FROM pg_catalog.pg_policies
             WHERE schemaname = 'ofarm'
               AND policyname LIKE
                   'tenant_command_runtime_bundle%runtime_reader_owner'
             ORDER BY tablename, policyname
            """
        ).fetchall()

    assert routine == (
        "ofarm_owner",
        "plpgsql",
        True,
        "s",
        "u",
        ["search_path=pg_catalog, pg_temp"],
        (
            "TABLE(tenant_id uuid, tenant_ref text, selection_binding_id text, "
            "selection_binding_canonical_digest text, command_id text, "
            "command_binding_id text, command_binding_canonical_digest text, "
            "selection_batch_id text, selection_knowledge_position bigint, "
            "runtime_bundle_digest text, selection_knowledge_cut bigint)"
        ),
        "",
    )
    assert acl == [
        ("ofarm_app", "EXECUTE", False),
        ("ofarm_owner", "EXECUTE", False),
        ("ofarm_worker", "EXECUTE", False),
    ]
    assert len(policies) == 2
    assert {row[0] for row in policies} == {
        "governed_write_batch",
        "tenant_command_runtime_bundle_selection",
    }
    assert all(
        row[2:] and row[2] == "PERMISSIVE"
        and row[3] == ["ofarm_owner"]
        and row[4] == "SELECT"
        and row[5] is not None
        and row[6] is None
        for row in policies
    )


def test_other_tenant_absence_is_one_opaque_refusal(
    target: TenantTarget,
    other_tenant_authority: TenantAuthority,
    active_selection,
    manager: TenantUnitOfWorkManager,
    migrated_audit_service,
    monkeypatch,
) -> None:
    del active_selection
    with psycopg.connect(target.role_dsn("ofarm_app")) as connection:
        _install_test_bound_context(connection, other_tenant_authority)
        assert connection.execute(f"SELECT * FROM {_RESOLVER}").fetchall() == []
    before = _tenant_state(
        target,
        other_tenant_authority.tenant_id,
        migrated_audit_service,
    )
    principal = _principal(target, other_tenant_authority)
    runtime, observed, request_router = _runtime(
        manager,
        migrated_audit_service,
        monkeypatch,
    )
    with runtime.tenant_unit_of_work(principal) as unit:
        for _attempt in range(2):
            with pytest.raises(CommandRuntimeBundleSelectionRefused) as raised:
                unit.resolve_commit_operation_claim_draft_runtime_bundle()
            assert str(raised.value) == raised.value.outcome
            assert raised.value.__cause__ is None
        with pytest.raises(RuntimeError, match="rollback-only"):
            unit.begin_batch(
                GovernedBatchRequest(
                    f"batch-selector-absent-{uuid4().hex}",
                    "SELECTOR_ABSENT_FALLBACK",
                    f"request-selector-absent-{uuid4().hex}",
                    other_tenant_authority.runtime_bundle_digest,
                )
            )

    assert observed == [(request_router, principal)]
    assert _tenant_state(
        target,
        other_tenant_authority.tenant_id,
        migrated_audit_service,
    ) == before


def test_database_read_failure_stays_opaque_and_rolls_back_without_audit(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
    active_selection,
    manager: TenantUnitOfWorkManager,
    migrated_audit_service,
    monkeypatch,
) -> None:
    del active_selection
    before = _tenant_state(
        target,
        tenant_authority.tenant_id,
        migrated_audit_service,
    )
    principal = _principal(target, tenant_authority)
    runtime, observed, request_router = _runtime(
        manager,
        migrated_audit_service,
        monkeypatch,
    )
    _set_app_resolver_execute(target, granted=False)
    try:
        with runtime.tenant_unit_of_work(principal) as unit:
            for _attempt in range(2):
                with pytest.raises(CommandRuntimeBundleSelectionRefused) as raised:
                    unit.resolve_commit_operation_claim_draft_runtime_bundle()
                assert str(raised.value) == raised.value.outcome
                assert raised.value.__cause__ is None
            with pytest.raises(RuntimeError, match="rollback-only"):
                unit.begin_batch(
                    GovernedBatchRequest(
                        f"batch-selector-db-failure-{uuid4().hex}",
                        "SELECTOR_DATABASE_FAILURE_FALLBACK",
                        f"request-selector-db-failure-{uuid4().hex}",
                        tenant_authority.runtime_bundle_digest,
                    )
                )
    finally:
        _set_app_resolver_execute(target, granted=True)

    assert observed == [(request_router, principal)]
    assert _tenant_state(
        target,
        tenant_authority.tenant_id,
        migrated_audit_service,
    ) == before


def test_database_and_uow_ordering_guards_refuse_after_batch(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
    active_selection,
    manager: TenantUnitOfWorkManager,
) -> None:
    del active_selection
    raw_batch = f"batch-selector-guard-{uuid4().hex}"
    with psycopg.connect(target.role_dsn("ofarm_app")) as connection:
        _install_test_bound_context(connection, tenant_authority)
        _insert_batch(connection, tenant_authority, raw_batch)
        assert connection.execute(f"SELECT * FROM {_RESOLVER}").fetchall() == []
        connection.rollback()

    managed_batch = f"batch-selector-uow-{uuid4().hex}"
    with manager.unit_of_work(_principal(target, tenant_authority)) as unit:
        unit.begin_batch(
            GovernedBatchRequest(
                managed_batch,
                "SELECTOR_ORDERING_GUARD",
                f"request-selector-{uuid4().hex}",
                tenant_authority.runtime_bundle_digest,
            )
        )
        with pytest.raises(CommandRuntimeBundleSelectionRefused):
            unit.resolve_commit_operation_claim_draft_runtime_bundle()
    with psycopg.connect(target.target_admin_dsn) as connection:
        assert connection.execute(
            "SELECT count(*) FROM ofarm.governed_write_batch "
            "WHERE tenant_id = %s AND batch_id = %s",
            (tenant_authority.tenant_id, managed_batch),
        ).fetchone() == (0,)


def test_new_uow_observes_later_head_without_changing_selection(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
    active_selection,
    manager: TenantUnitOfWorkManager,
) -> None:
    principal = _principal(target, tenant_authority)
    with manager.unit_of_work(principal) as unit:
        first = unit.resolve_commit_operation_claim_draft_runtime_bundle()
    batch_id = f"batch-selector-later-{uuid4().hex}"
    with psycopg.connect(target.role_dsn("ofarm_app")) as connection:
        _install_test_bound_context(connection, tenant_authority)
        _insert_batch(connection, tenant_authority, batch_id)
    with manager.unit_of_work(principal) as unit:
        later = unit.resolve_commit_operation_claim_draft_runtime_bundle()

    assert later.selection_batch_id == active_selection.selection_batch_id
    assert later.runtime_bundle_digest == first.runtime_bundle_digest
    assert later.selection_knowledge_cut == first.selection_knowledge_cut + 1


def test_concurrent_activation_is_absent_or_complete_and_extra_is_inert(
    target: TenantTarget,
    other_tenant_authority: TenantAuthority,
    selected_bundle,
) -> None:
    extended = _extended_command_selection_bundle(
        selected_bundle,
        logical_ref=f"rules/reference#selector-extra-{uuid4().hex}",
    )
    with psycopg.connect(target.target_admin_dsn) as connection:
        _publish_model_runtime_bundle(
            connection,
            other_tenant_authority.tenant_id,
            extended,
        )
    barrier = threading.Barrier(2)

    def read() -> list[tuple[object, ...]]:
        with psycopg.connect(target.role_dsn("ofarm_worker")) as connection:
            _install_test_bound_context(connection, other_tenant_authority)
            barrier.wait()
            return connection.execute(f"SELECT * FROM {_RESOLVER}").fetchall()

    def activate():
        with psycopg.connect(
            target.role_dsn(
                "ofarm_command_runtime_bundle_selection_control_login"
            )
        ) as connection:
            _install_test_bound_context(connection, other_tenant_authority)
            barrier.wait()
            return control.activate_commit_operation_claim_draft_runtime_bundle_selection(
                connection,
                extended,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        read_future = executor.submit(read)
        activate_future = executor.submit(activate)
        observed = read_future.result(timeout=10)
        selected = activate_future.result(timeout=10)

    assert observed == [] or (
        len(observed) == 1
        and observed[0][0] == other_tenant_authority.tenant_id
        and observed[0][7] == selected.selection_batch_id
        and observed[0][8] == selected.selection_knowledge_position
        and observed[0][9] == extended.digest
        and observed[0][8] <= observed[0][10]
    )
    with psycopg.connect(target.role_dsn("ofarm_worker")) as connection:
        _install_test_bound_context(connection, other_tenant_authority)
        resolved = _resolve_commit_operation_claim_draft_runtime_bundle(
            connection,
            other_tenant_authority.tenant_id,
        )
    assert resolved.runtime_bundle == extended
    assert len(resolved.runtime_bundle.components) == 17
    assert resolved.selection_batch_id == selected.selection_batch_id
