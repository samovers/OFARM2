"""Real-role evidence for the current-transaction challenge observation."""

from __future__ import annotations

from uuid import UUID

import psycopg
import pytest
from psycopg import sql

from kernel.tests.test_postgresql_tenant_migration import (
    CapabilityKeyAuthority,
    TenantAuthority,
    TenantTarget,
    _signed_capability_for_new_challenge,
    authority,  # noqa: F401 - imported fixture
    capability_key,  # noqa: F401 - imported fixture
    tenant_target,  # noqa: F401 - imported fixture
)


_OBSERVE = "SELECT * FROM ofarm.current_tenant_challenge()"
_CURRENT_XID = "SELECT pg_catalog.pg_current_xact_id_if_assigned()::text"


@pytest.fixture(scope="module")
def target(request) -> TenantTarget:
    return request.getfixturevalue("tenant_target")


@pytest.fixture(scope="module")
def tenant_authority(request) -> TenantAuthority:
    return request.getfixturevalue("authority")


@pytest.fixture(scope="module")
def key_authority(request) -> CapabilityKeyAuthority:
    return request.getfixturevalue("capability_key")


def _observe(connection: psycopg.Connection) -> tuple[UUID, int]:
    cursor = connection.execute(_OBSERVE)
    assert tuple(column.name for column in cursor.description) == (
        "challenge_id",
        "challenge_created_at_unix_microseconds",
    )
    rows = cursor.fetchall()
    assert len(rows) == 1
    challenge_id, created_at = rows[0]
    assert isinstance(challenge_id, UUID)
    assert type(created_at) is int
    return challenge_id, created_at


def _refuse(connection: psycopg.Connection) -> str:
    """A savepoint lets the caller inspect its unchanged transaction afterward."""
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState) as refused:
        with connection.transaction():
            connection.execute(_OBSERVE)
    assert refused.value.sqlstate == "55000"
    assert refused.value.diag.message_primary == (
        "current tenant challenge is unavailable"
    )
    return refused.value.diag.message_primary


def _stored_challenge(
    target: TenantTarget, challenge_id: UUID
) -> tuple[UUID, int, str]:
    # Inspect only after the runtime transaction commits. No read privilege or
    # test-only routine is installed in the application/worker session.
    with psycopg.connect(target.target_admin_dsn) as admin:
        rows = admin.execute(
            """
            SELECT context.challenge_id,
                   (extract(epoch FROM context.challenge_created_at) *
                    1000000)::pg_catalog.int8,
                   context.context_state
            FROM ofarm.tenant_binding_context AS context
            WHERE context.challenge_id = %s
            """,
            (challenge_id,),
        ).fetchall()
    assert len(rows) == 1
    return rows[0]


@pytest.mark.parametrize("role_name", ("ofarm_app", "ofarm_worker"))
def test_observation_returns_exact_stored_metadata_without_renewing(
    target: TenantTarget, role_name: str
) -> None:
    with psycopg.connect(target.role_dsn(role_name)) as runtime:
        cursor = runtime.execute("SELECT * FROM ofarm.create_tenant_challenge()")
        assert tuple(column.name for column in cursor.description) == (
            "challenge_id", "audience"
        )
        challenge_id, audience = cursor.fetchone()
        assert isinstance(audience, str)
        first = _observe(runtime)
        xid = runtime.execute(_CURRENT_XID).fetchone()
        runtime.execute("SELECT pg_catalog.pg_sleep(0.01)")
        for _ in range(3):
            assert _observe(runtime) == first
            assert runtime.execute(_CURRENT_XID).fetchone() == xid
        assert first[0] == challenge_id
        runtime.commit()
        assert _stored_challenge(target, challenge_id) == (
            *first, "CHALLENGE"
        )


def test_expired_worker_challenge_remains_observable_without_renewal(
    target: TenantTarget,
) -> None:
    # The existing worker limits allow 120s transactions and 60s statements.
    # Keep the transaction active while crossing the genuine 60s challenge
    # window; do not alter a protected timestamp or any role timeout.
    with psycopg.connect(target.role_dsn("ofarm_worker")) as worker:
        worker.execute("SELECT * FROM ofarm.create_tenant_challenge()")
        original = _observe(worker)
        for _ in range(2):
            worker.execute("SELECT pg_catalog.pg_sleep(31)")
            assert _observe(worker) == original
        now_us = worker.execute(
            """
            SELECT (extract(epoch FROM pg_catalog.clock_timestamp()) *
                    1000000)::pg_catalog.int8
            """
        ).fetchone()[0]
        assert now_us > original[1] + 60_000_000
        worker.commit()
        assert _stored_challenge(target, original[0]) == (
            *original, "CHALLENGE"
        )


@pytest.mark.parametrize("role_name", ("ofarm_app", "ofarm_worker"))
def test_absent_observation_never_assigns_a_transaction_id(
    target: TenantTarget, role_name: str
) -> None:
    with psycopg.connect(target.role_dsn(role_name)) as runtime:
        assert runtime.execute(_CURRENT_XID).fetchone() == (None,)
        no_xid_message = _refuse(runtime)
        assert runtime.execute(_CURRENT_XID).fetchone() == (None,)
        assigned = runtime.execute(
            "SELECT pg_catalog.pg_current_xact_id()::text"
        ).fetchone()
        assert _refuse(runtime) == no_xid_message
        assert runtime.execute(_CURRENT_XID).fetchone() == assigned


@pytest.mark.parametrize("finish", ("commit", "rollback"))
def test_previous_transaction_challenge_cannot_be_observed(
    target: TenantTarget, finish: str
) -> None:
    with psycopg.connect(target.role_dsn("ofarm_app")) as runtime:
        runtime.execute("SELECT * FROM ofarm.create_tenant_challenge()")
        original = _observe(runtime)
        original_xid = runtime.execute(_CURRENT_XID).fetchone()
        getattr(runtime, finish)()
        assert runtime.execute(_CURRENT_XID).fetchone() == (None,)
        _refuse(runtime)
        assert runtime.execute(_CURRENT_XID).fetchone() == (None,)
        next_xid = runtime.execute(
            "SELECT pg_catalog.pg_current_xact_id()::text"
        ).fetchone()
        assert next_xid != original_xid
        _refuse(runtime)
        runtime.execute("SELECT * FROM ofarm.create_tenant_challenge()")
        assert _observe(runtime)[0] != original[0]


def test_savepoint_rollback_preserves_only_the_top_level_challenge(
    target: TenantTarget,
) -> None:
    with psycopg.connect(target.role_dsn("ofarm_app")) as runtime:
        runtime.execute("SAVEPOINT before_challenge")
        runtime.execute("SELECT * FROM ofarm.create_tenant_challenge()")
        rolled_back = _observe(runtime)
        top_xid = runtime.execute(_CURRENT_XID).fetchone()
        runtime.execute("ROLLBACK TO SAVEPOINT before_challenge")
        assert runtime.execute(_CURRENT_XID).fetchone() == top_xid
        _refuse(runtime)
        runtime.execute("SELECT * FROM ofarm.create_tenant_challenge()")
        retained = _observe(runtime)
        assert retained[0] != rolled_back[0]
        runtime.execute("SAVEPOINT after_challenge")
        assert _observe(runtime) == retained
        runtime.execute("ROLLBACK TO SAVEPOINT after_challenge")
        assert _observe(runtime) == retained
        assert runtime.execute(_CURRENT_XID).fetchone() == top_xid


def test_simultaneous_sessions_observe_only_their_own_challenge(
    target: TenantTarget,
) -> None:
    with (
        psycopg.connect(target.role_dsn("ofarm_app")) as first,
        psycopg.connect(target.role_dsn("ofarm_app")) as peer,
        psycopg.connect(target.role_dsn("ofarm_worker")) as worker,
    ):
        first.execute("SELECT * FROM ofarm.create_tenant_challenge()")
        first_observation = _observe(first)
        for connection in (peer, worker):
            # Even an assigned peer transaction has no selectable row.
            connection.execute("SELECT pg_catalog.pg_current_xact_id()")
            _refuse(connection)
            connection.execute("SELECT * FROM ofarm.create_tenant_challenge()")
        peer_observation = _observe(peer)
        worker_observation = _observe(worker)
        assert len({
            first_observation[0], peer_observation[0], worker_observation[0]
        }) == 3
        for _ in range(3):
            assert _observe(first) == first_observation
            assert _observe(peer) == peer_observation
            assert _observe(worker) == worker_observation


@pytest.mark.parametrize("role_name", ("ofarm_app", "ofarm_worker"))
def test_successful_existing_bind_consumes_observable_challenge(
    target: TenantTarget,
    tenant_authority: TenantAuthority,
    key_authority: CapabilityKeyAuthority,
    role_name: str,
) -> None:
    with psycopg.connect(target.role_dsn(role_name)) as runtime:
        absent_message = _refuse(runtime)
        token = _signed_capability_for_new_challenge(
            runtime, authority=tenant_authority, key=key_authority
        )
        before = _observe(runtime)
        runtime.execute("SELECT ofarm.bind_tenant_capability(%s)", (token,))
        assert runtime.execute("SELECT ofarm.current_tenant_id()").fetchone() == (
            tenant_authority.tenant_id,
        )
        assert _refuse(runtime) == absent_message
        runtime.commit()
        assert _stored_challenge(target, before[0]) == (*before, "BOUND")


def test_observation_has_one_closed_function_acl_and_no_observer_membership(
    target: TenantTarget,
) -> None:
    with psycopg.connect(target.target_admin_dsn) as admin:
        assert admin.execute(
            """
            SELECT owner.rolname::text,
                   pg_catalog.pg_get_function_identity_arguments(routine.oid),
                   pg_catalog.pg_get_function_result(routine.oid),
                   routine.prosecdef, routine.provolatile, routine.proparallel,
                   routine.proconfig
            FROM pg_catalog.pg_proc AS routine
            JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
            WHERE routine.oid =
                'ofarm.current_tenant_challenge()'::pg_catalog.regprocedure
            """
        ).fetchone() == (
            "ofarm_owner", "",
            "TABLE(challenge_id uuid, "
            "challenge_created_at_unix_microseconds bigint)",
            True, "s", "u", ["search_path=pg_catalog, pg_temp"],
        )
        assert admin.execute(
            """
            SELECT CASE WHEN acl.grantee = 0 THEN 'PUBLIC'
                        ELSE grantee.rolname::text END,
                   grantor.rolname::text, acl.privilege_type, acl.is_grantable
            FROM pg_catalog.pg_proc AS routine
            CROSS JOIN LATERAL pg_catalog.aclexplode(routine.proacl) AS acl
            LEFT JOIN pg_catalog.pg_roles AS grantee ON grantee.oid = acl.grantee
            JOIN pg_catalog.pg_roles AS grantor ON grantor.oid = acl.grantor
            WHERE routine.oid =
                'ofarm.current_tenant_challenge()'::pg_catalog.regprocedure
            ORDER BY 1, 2, 3, 4
            """
        ).fetchall() == [
            (role, "ofarm_owner", "EXECUTE", False)
            for role in ("ofarm_app", "ofarm_owner", "ofarm_worker")
        ]
        for role in ("ofarm_app", "ofarm_worker", "ofarm_owner"):
            assert admin.execute(
                "SELECT pg_catalog.pg_has_role(%s, "
                "'ofarm_backend_observer', 'MEMBER')",
                (role,),
            ).fetchone() == (False,)


@pytest.mark.parametrize("role_name", ("ofarm_app", "ofarm_worker"))
def test_runtime_observation_adds_no_raw_table_or_custody_privilege(
    target: TenantTarget, role_name: str
) -> None:
    denied = (
        "SELECT * FROM ofarm.tenant_binding_context",
        "SELECT * FROM pg_catalog.pg_stat_activity",
        "SELECT ofarm.current_backend_start()",
        "CREATE TEMP TABLE forbidden_challenge_context (value integer)",
        "SET ROLE ofarm_owner",
        "SET ROLE ofarm_binder",
        "SET ROLE ofarm_backend_observer",
        """
        CREATE OR REPLACE FUNCTION ofarm.current_tenant_challenge()
        RETURNS TABLE (challenge_id uuid,
                       challenge_created_at_unix_microseconds bigint)
        LANGUAGE sql AS 'SELECT NULL::uuid, 0::bigint'
        """,
    )
    with psycopg.connect(target.role_dsn(role_name)) as runtime:
        for statement in denied:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with runtime.transaction():
                    runtime.execute(statement)


@pytest.mark.parametrize("role_name", (
    "ofarm_identity_control_login",
    "ofarm_tenant_control_login",
    "ofarm_capability_key_control_login",
    "ofarm_command_runtime_bundle_selection_control_login",
))
def test_unrelated_controller_logins_cannot_observe_challenges(
    target: TenantTarget, role_name: str
) -> None:
    with psycopg.connect(target.role_dsn(role_name)) as controller:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            controller.execute(_OBSERVE)


@pytest.mark.parametrize("role_name", ("ofarm_app", "ofarm_worker"))
def test_temp_objects_and_caller_search_path_cannot_substitute_metadata(
    target: TenantTarget, role_name: str
) -> None:
    # Runtime roles cannot create temporary objects. Prepare contamination as
    # the trusted fixture administrator, then change session authorization;
    # the observed operation runs with the runtime role's SQL privileges.
    with psycopg.connect(target.target_admin_dsn) as runtime:
        runtime.execute(
            "CREATE TEMP TABLE tenant_binding_context "
            "(challenge_id uuid, challenge_created_at timestamptz)"
        )
        runtime.execute(
            "INSERT INTO tenant_binding_context VALUES "
            "('00000000-0000-0000-0000-000000000001', "
            "'2000-01-01 00:00:00+00')"
        )
        runtime.execute(
            "CREATE FUNCTION pg_temp.pg_backend_pid() RETURNS integer "
            "LANGUAGE sql AS 'SELECT -1'"
        )
        runtime.execute(
            "CREATE FUNCTION pg_temp.pg_current_xact_id_if_assigned() "
            "RETURNS xid8 LANGUAGE sql AS 'SELECT NULL::xid8'"
        )
        runtime.execute(
            sql.SQL("SET SESSION AUTHORIZATION {}").format(
                sql.Identifier(role_name)
            )
        )
        assert runtime.execute("SELECT CURRENT_USER, SESSION_USER").fetchone() == (
            role_name, role_name
        )
        runtime.execute("SELECT * FROM ofarm.create_tenant_challenge()")
        expected = _observe(runtime)
        runtime.execute("SET LOCAL search_path = pg_temp, public")
        assert _observe(runtime) == expected


def test_observation_acquires_no_row_or_advisory_lock(
    target: TenantTarget,
) -> None:
    with (
        psycopg.connect(target.role_dsn("ofarm_app")) as runtime,
        psycopg.connect(target.target_admin_dsn) as admin,
    ):
        runtime.execute("SELECT * FROM ofarm.create_tenant_challenge()")
        backend_pid = runtime.info.backend_pid
        locks = """
            SELECT locktype, mode, granted, relation, page, tuple, classid, objid
            FROM pg_catalog.pg_locks
            WHERE pid = %s AND locktype IN ('tuple', 'advisory')
            ORDER BY 1, 2, 3, 4, 5, 6, 7, 8
        """
        before = admin.execute(locks, (backend_pid,)).fetchall()
        assert before == []
        observation = _observe(runtime)
        assert admin.execute(locks, (backend_pid,)).fetchall() == before
        runtime.commit()
        # PostgreSQL need not expose an uncontended row lock in pg_locks.
        # A row-locking observation would also mark this inserted tuple's xmax.
        assert admin.execute(
            "SELECT xmax::text FROM ofarm.tenant_binding_context "
            "WHERE challenge_id = %s",
            (observation[0],),
        ).fetchone() == ("0",)
