"""Real PostgreSQL 17 migration-runner boundary tests for issue #174.

Most migrations used here are synthetic and live under pytest's temporary
directory.  The release-upgrade regression reads the authoritative tenant
history but never writes either checked-in migration directory.
"""

from __future__ import annotations

import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from uuid import UUID, uuid4

import psycopg
import psycopg.conninfo
import pytest
from psycopg import sql

import deployment.postgresql.migration_runner as migration_runner_module
import deployment.postgresql.provisioning as provisioning_module
from deployment.postgresql.migration_runner import (
    MigrationDirtyError,
    MigrationError,
    MigrationExecutionError,
    MigrationInfrastructureTransitionOutcomeUnknown,
    MigrationInputError,
    MigrationOutcomeUnknown,
    MigrationRunReport,
    MigrationTargetError,
    _begin_and_lock,
    _migrate_service_for_testing as migrate_service,
    initial_ledger_sql,
    migrate_service as migrate_authoritative_service,
    validate_migration_source,
)
from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_SERVICE,
    TENANT_SERVICE,
    MigrationService,
    MigrationSet,
    load_migration_set,
)
from deployment.postgresql.provisioning import (
    ProvisioningDriftError,
    provision_service,
    verify_service,
    verify_service_infrastructure,
)
from deployment.postgresql.provisioning_specs import (
    SECURITY_AUDIT_PROVISIONING_SPEC,
    TENANT_PROVISIONING_SPEC,
    TENANT_PROVISIONING_SPEC_V1,
    ProvisioningSpec,
)
from deployment.postgresql.version_policy import (
    SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
)


TENANT_ADMIN_ENV = "OFARM_TENANT_PROVISIONING_PG_ADMIN_DSN"
AUDIT_ADMIN_ENV = "OFARM_SECURITY_AUDIT_PG_ADMIN_DSN"
MAINTENANCE_DATABASES = ("postgres", "template0", "template1")
RELEASE_IDENTITY = "ofarm-tests/issue-174"


class _FailingTransactionSetup:
    def __init__(self, failure_prefix: str) -> None:
        self.failure_prefix = failure_prefix
        self.rolled_back = False

    def execute(self, statement):
        rendered = str(statement)
        if rendered.startswith(self.failure_prefix):
            raise psycopg.OperationalError("SECRET-TRANSACTION-SETUP-SENTINEL")
        return self

    def fetchone(self):
        return (None,)

    def rollback(self) -> None:
        self.rolled_back = True


@pytest.mark.parametrize("failure_prefix", ("BEGIN", "SET LOCAL"))
def test_transaction_setup_failures_are_normalized_and_rolled_back(
    failure_prefix: str,
) -> None:
    connection = _FailingTransactionSetup(failure_prefix)

    with pytest.raises(
        MigrationTargetError,
        match="protected migration transaction setup failed",
    ) as raised:
        _begin_and_lock(connection, TENANT_PROVISIONING_SPEC)  # type: ignore[arg-type]

    assert connection.rolled_back is True
    assert "SECRET-TRANSACTION-SETUP-SENTINEL" not in str(raised.value)


@dataclass(frozen=True, slots=True)
class _TenantTarget:
    admin_dsn: str
    target_admin_dsn: str
    migrator_dsn: str
    passwords: Mapping[str, str]


def _admin_dsn() -> str:
    value = os.environ.get(TENANT_ADMIN_ENV)
    if value:
        return value
    raise RuntimeError(
        f"{TENANT_ADMIN_ENV} must identify a dedicated PostgreSQL 17 service"
    )


def _audit_admin_dsn() -> str:
    value = os.environ.get(AUDIT_ADMIN_ENV)
    if value:
        return value
    raise RuntimeError(
        f"{AUDIT_ADMIN_ENV} must identify a dedicated PostgreSQL 17 service"
    )


def _database_dsn(admin_dsn: str, database_name: str, **overrides: str) -> str:
    parameters = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    parameters["dbname"] = database_name
    parameters.update(overrides)
    return psycopg.conninfo.make_conninfo(**parameters)


def _assert_clean_service(admin_dsn: str, spec: ProvisioningSpec) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        database = connection.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            (spec.database_name,),
        ).fetchone()
        roles = connection.execute(
            r"""
            SELECT rolname::text
            FROM pg_catalog.pg_roles
            WHERE rolname::text LIKE 'ofarm\_%' ESCAPE '\'
            ORDER BY rolname
            """
        ).fetchall()
        databases = connection.execute(
            "SELECT datname::text FROM pg_catalog.pg_database ORDER BY datname"
        ).fetchall()
        public_database_privileges = connection.execute(
            """
            SELECT database.datname::text, acl.privilege_type
            FROM pg_catalog.pg_database AS database
            CROSS JOIN LATERAL pg_catalog.aclexplode(
                COALESCE(
                    database.datacl,
                    pg_catalog.acldefault('d', database.datdba)
                )
            ) AS acl
            WHERE database.datname = ANY (%s::text[])
              AND acl.grantee = 0
            ORDER BY 1, 2
            """,
            (list(MAINTENANCE_DATABASES),),
        ).fetchall()
    assert database is None, (
        f"disposable database already exists: {spec.database_name}"
    )
    assert roles == [], f"disposable service has governed roles: {roles}"
    assert databases == [(name,) for name in MAINTENANCE_DATABASES]
    assert public_database_privileges == [
        ("postgres", "CONNECT"),
        ("postgres", "TEMPORARY"),
        ("template0", "CONNECT"),
        ("template1", "CONNECT"),
    ]


def _destroy_test_service(admin_dsn: str, spec: ProvisioningSpec) -> None:
    """Remove only the fixed disposable resources this module provisioned."""

    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        role_names = [
            row[0]
            for row in connection.execute(
                r"""
                SELECT rolname::text
                FROM pg_catalog.pg_roles
                WHERE rolname::text LIKE 'ofarm\_%' ESCAPE '\'
                ORDER BY rolname
                """
            ).fetchall()
        ]
        unexpected_roles = sorted(set(role_names) - set(spec.role_names))
        if unexpected_roles:
            raise AssertionError(
                "refusing disposable cleanup with unexpected governed roles: "
                f"{unexpected_roles}"
            )
        connection.execute(
            """
            SELECT pg_catalog.pg_terminate_backend(pid)
            FROM pg_catalog.pg_stat_activity
            WHERE datname = %s AND pid <> pg_catalog.pg_backend_pid()
            """,
            (spec.database_name,),
        )
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(spec.database_name)
            )
        )
        if role_names:
            connection.execute(
                sql.SQL("DROP ROLE {}").format(
                    sql.SQL(", ").join(
                        sql.Identifier(role_name) for role_name in role_names
                    )
                )
            )
        for maintenance_database in MAINTENANCE_DATABASES:
            connection.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO PUBLIC").format(
                    sql.Identifier(maintenance_database)
                )
            )
        connection.execute("GRANT TEMPORARY ON DATABASE postgres TO PUBLIC")
        connection.execute(
            "REVOKE TEMPORARY ON DATABASE template0, template1 FROM PUBLIC"
        )


def _passwords(spec: ProvisioningSpec, nonce: str) -> dict[str, str]:
    return {
        role_name: f"{nonce}-{index}-{secrets.token_urlsafe(32)}"
        for index, role_name in enumerate(spec.required_password_role_names)
    }


@pytest.fixture
def tenant_target() -> _TenantTarget:
    admin_dsn = _admin_dsn()
    spec = TENANT_PROVISIONING_SPEC
    _assert_clean_service(admin_dsn, spec)
    passwords = _passwords(spec, "migration-runner-" + secrets.token_urlsafe(12))
    try:
        provision_service(admin_dsn, spec, login_passwords=passwords)
        yield _TenantTarget(
            admin_dsn=admin_dsn,
            target_admin_dsn=_database_dsn(admin_dsn, spec.database_name),
            migrator_dsn=_database_dsn(
                admin_dsn,
                spec.database_name,
                user="ofarm_migrator",
                password=passwords["ofarm_migrator"],
            ),
            passwords=passwords,
        )
    finally:
        _destroy_test_service(admin_dsn, spec)


@pytest.fixture
def tenant_v1_target() -> _TenantTarget:
    admin_dsn = _admin_dsn()
    old_spec = TENANT_PROVISIONING_SPEC_V1
    _assert_clean_service(admin_dsn, old_spec)
    passwords = _passwords(
        old_spec,
        "migration-runner-v1-" + secrets.token_urlsafe(12),
    )
    try:
        provision_service(admin_dsn, old_spec, login_passwords=passwords)
        yield _TenantTarget(
            admin_dsn=admin_dsn,
            target_admin_dsn=_database_dsn(
                admin_dsn,
                old_spec.database_name,
            ),
            migrator_dsn=_database_dsn(
                admin_dsn,
                old_spec.database_name,
                user="ofarm_migrator",
                password=passwords["ofarm_migrator"],
            ),
            passwords=passwords,
        )
    finally:
        _destroy_test_service(admin_dsn, TENANT_PROVISIONING_SPEC)


@pytest.fixture
def audit_target() -> _TenantTarget:
    admin_dsn = _audit_admin_dsn()
    spec = SECURITY_AUDIT_PROVISIONING_SPEC
    _assert_clean_service(admin_dsn, spec)
    passwords = _passwords(spec, "audit-runner-" + secrets.token_urlsafe(12))
    try:
        provision_service(admin_dsn, spec, login_passwords=passwords)
        yield _TenantTarget(
            admin_dsn=admin_dsn,
            target_admin_dsn=_database_dsn(admin_dsn, spec.database_name),
            migrator_dsn=_database_dsn(
                admin_dsn,
                spec.database_name,
                user="ofarm_migrator",
                password=passwords["ofarm_migrator"],
            ),
            passwords=passwords,
        )
    finally:
        _destroy_test_service(admin_dsn, spec)


def _load_synthetic_set(
    tmp_path: Path,
    sources: Mapping[str, bytes],
    *,
    service: MigrationService = TENANT_SERVICE,
) -> MigrationSet:
    package_root = tmp_path / "synthetic-package"
    directory = package_root.joinpath(*service.relative_directory.split("/"))
    directory.mkdir(parents=True)
    for filename, source_bytes in sources.items():
        (directory / filename).write_bytes(source_bytes)
    return load_migration_set(package_root, service)


def _initial_source(*, delay_seconds: float | None = None) -> bytes:
    source = initial_ledger_sql(TENANT_PROVISIONING_SPEC).encode("utf-8")
    if delay_seconds is not None:
        source += f"\nSELECT pg_catalog.pg_sleep({delay_seconds});\n".encode("ascii")
    source += b"""
CREATE FUNCTION ofarm.create_tenant_challenge()
RETURNS pg_catalog.uuid
LANGUAGE sql VOLATILE PARALLEL UNSAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'SELECT NULL::pg_catalog.uuid';

CREATE FUNCTION ofarm.current_tenant_id()
RETURNS pg_catalog.uuid
LANGUAGE sql STABLE PARALLEL UNSAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'SELECT NULL::pg_catalog.uuid';

CREATE FUNCTION ofarm.current_backend_start()
RETURNS pg_catalog.timestamptz
LANGUAGE sql STABLE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'SELECT pg_catalog.clock_timestamp()';

CREATE FUNCTION ofarm.backend_incarnation_is_live(
    pg_catalog.int4,
    pg_catalog.timestamptz
)
RETURNS pg_catalog.bool
LANGUAGE sql STABLE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'SELECT TRUE';

CREATE FUNCTION ofarm.validate_promotion_edge()
RETURNS pg_catalog.trigger
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'BEGIN RETURN NEW; END';

CREATE FUNCTION ofarm.require_promotion_reachability()
RETURNS pg_catalog.trigger
LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'BEGIN RETURN NEW; END';

CREATE FUNCTION ofarm.take_tenant_write_lock()
RETURNS pg_catalog.void
LANGUAGE sql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'SELECT pg_catalog.pg_sleep(0)';

CREATE TABLE ofarm.migration_runner_probe (
    probe_id pg_catalog.int4 PRIMARY KEY,
    value pg_catalog.text NOT NULL
);
"""
    existing_routine_identities = {
        ("create_tenant_challenge", ()),
        ("current_tenant_id", ()),
        ("current_backend_start", ()),
        (
            "backend_incarnation_is_live",
            ("integer", "timestamp with time zone"),
        ),
        ("validate_promotion_edge", ()),
        ("require_promotion_reachability", ()),
        ("take_tenant_write_lock", ()),
    }
    sealer = TENANT_PROVISIONING_SPEC.tenant_initial_owner_sealer
    assert sealer is not None
    for transfer in sealer.transfers:
        identity = (transfer.function_name, transfer.argument_types)
        if identity in existing_routine_identities:
            continue
        source += (
            f"""
CREATE FUNCTION {transfer.qualified_identity}
RETURNS pg_catalog.void
LANGUAGE sql VOLATILE PARALLEL UNSAFE SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS 'SELECT pg_catalog.pg_sleep(0)';
"""
        ).encode("ascii")
    return source


def _run(
    target: _TenantTarget,
    migration_set: MigrationSet,
    *,
    execution_id: UUID | None = None,
    release_identity: str = RELEASE_IDENTITY,
    spec: ProvisioningSpec = TENANT_PROVISIONING_SPEC,
) -> MigrationRunReport:
    return migrate_service(
        admin_dsn=target.admin_dsn,
        migrator_dsn=target.migrator_dsn,
        spec=spec,
        migration_set=migration_set,
        release_identity=release_identity,
        execution_id=execution_id or uuid4(),
    )


def _ledger_rows(target: _TenantTarget) -> list[tuple[object, ...]]:
    with psycopg.connect(target.target_admin_dsn) as connection:
        return connection.execute(
            """
            SELECT version,
                   filename,
                   source_sha256,
                   source_byte_length,
                   applied_prefix_digest,
                   service_identity,
                   provisioning_spec_digest,
                   release_identity,
                   execution_id::text
            FROM ofarm.schema_migration
            ORDER BY version
            """
        ).fetchall()


def _relation_exists(target: _TenantTarget, qualified_name: str) -> bool:
    with psycopg.connect(target.target_admin_dsn) as connection:
        return connection.execute(
            "SELECT pg_catalog.to_regclass(%s) IS NOT NULL",
            (qualified_name,),
        ).fetchone()[0]


def _tamper_ledger_value(
    target: _TenantTarget,
    column: str,
    value: str,
    *,
    drop_fixed_constraint: bool,
) -> None:
    with psycopg.connect(target.target_admin_dsn, autocommit=True) as connection:
        if drop_fixed_constraint:
            constraints = connection.execute(
                """
                SELECT constraint_name.conname::text
                FROM pg_catalog.pg_constraint AS constraint_name
                WHERE constraint_name.conrelid =
                      'ofarm.schema_migration'::pg_catalog.regclass
                  AND constraint_name.contype = 'c'
                  AND pg_catalog.pg_get_constraintdef(
                          constraint_name.oid,
                          true
                      ) LIKE %s
                ORDER BY constraint_name.conname
                """,
                (f"%{column}%",),
            ).fetchall()
            assert constraints, f"no ledger constraint governs {column}"
            for (constraint_name,) in constraints:
                connection.execute(
                    sql.SQL(
                        "ALTER TABLE ofarm.schema_migration DROP CONSTRAINT {}"
                    ).format(sql.Identifier(constraint_name))
                )
        connection.execute(
            "ALTER TABLE ofarm.schema_migration "
            "DISABLE TRIGGER schema_migration_reject_update_delete"
        )
        connection.execute(
            sql.SQL(
                "UPDATE ofarm.schema_migration SET {} = %s WHERE version = 1"
            ).format(sql.Identifier(column)),
            (value,),
        )
        connection.execute(
            "ALTER TABLE ofarm.schema_migration "
            "ENABLE TRIGGER schema_migration_reject_update_delete"
        )


def test_source_validator_ignores_prohibited_words_inside_lexical_bodies():
    source = b"""
-- BEGIN; COMMIT; COPY hidden FROM STDIN;
/* ROLLBACK; /* SET ROLE hidden; */ SAVEPOINT hidden; */
SELECT 'START TRANSACTION; RESET ROLE;';
SELECT "COMMIT" FROM (SELECT 1 AS "COMMIT") AS quoted_identifier;
SELECT $body$PREPARE TRANSACTION 'hidden'; \\i hidden.sql$body$;
CREATE FUNCTION ofarm.example() RETURNS pg_catalog.void
LANGUAGE plpgsql AS $function$
BEGIN
    PERFORM 'ROLLBACK PREPARED';
END
$function$;
"""

    assert validate_migration_source(source, "0001_initial.sql") == source.decode(
        "utf-8"
    )


@pytest.mark.parametrize(
    "source",
    (
        b"BEGIN;",
        b"START TRANSACTION;",
        b"COMMIT;",
        b"END;",
        b"ROLLBACK;",
        b"ABORT;",
        b"SAVEPOINT migration_step;",
        b"RELEASE SAVEPOINT migration_step;",
        b"PREPARE TRANSACTION 'migration_step';",
        b"COMMIT PREPARED 'migration_step';",
        b"ROLLBACK PREPARED 'migration_step';",
        b"SET ROLE ofarm_owner;",
        b"RESET ROLE;",
        b"SET SESSION AUTHORIZATION ofarm_owner;",
        b"SET LOCAL SESSION AUTHORIZATION ofarm_owner;",
        b"RESET SESSION AUTHORIZATION;",
        b"SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;",
        b"SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY;",
        b"SET LOCAL synchronous_commit = off;",
        b"RESET ALL;",
        b"COPY ofarm.example FROM STDIN;",
        b"\\i hidden.sql\n",
        b"SELECT 1; -- hidden only until CR\rCOMMIT;",
    ),
)
def test_source_validator_rejects_runner_owned_or_client_side_control(
    source: bytes,
):
    with pytest.raises(MigrationInputError):
        validate_migration_source(source, "0001_initial.sql")


@pytest.mark.parametrize("source", (b"-- comment only\r", b"/* only */; ;"))
def test_source_validator_rejects_sources_without_a_sql_statement(source: bytes):
    with pytest.raises(MigrationInputError, match="no SQL statement"):
        validate_migration_source(source, "0001_initial.sql")


def test_cr_line_comment_control_refuses_before_any_target_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {
            "0001_initial.sql": (
                b"CREATE TABLE ofarm.partial (id pg_catalog.int4); "
                b"-- only until CR\rCOMMIT;"
            )
        },
    )

    def target_must_not_be_observed(*_args, **_kwargs):
        raise AssertionError("target was observed before SQL preflight completed")

    monkeypatch.setattr(
        migration_runner_module,
        "verify_service_infrastructure",
        target_must_not_be_observed,
    )
    with pytest.raises(MigrationInputError, match="runner-owned SQL control"):
        migrate_service(
            admin_dsn="must-not-connect",
            migrator_dsn="must-not-connect",
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=migration_set,
            release_identity=RELEASE_IDENTITY,
            execution_id=uuid4(),
        )


def test_public_runner_refuses_synthetic_history_before_target_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )

    def target_must_not_be_observed(*_args, **_kwargs):
        raise AssertionError("target was observed before release authentication")

    monkeypatch.setattr(
        migration_runner_module,
        "verify_service_infrastructure",
        target_must_not_be_observed,
    )
    with pytest.raises(MigrationInputError, match="authoritative release history"):
        migrate_authoritative_service(
            admin_dsn="must-not-connect",
            migrator_dsn="must-not-connect",
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=migration_set,
            release_identity=RELEASE_IDENTITY,
            execution_id=uuid4(),
        )


def test_applies_exact_0001_then_verifies_a_noop_without_creating_the_ledger(
    tenant_target: _TenantTarget,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )

    def _runner_must_not_create_ledger(_spec: ProvisioningSpec) -> str:
        raise AssertionError("the runner called the test-only ledger DDL helper")

    monkeypatch.setattr(
        migration_runner_module,
        "initial_ledger_sql",
        _runner_must_not_create_ledger,
    )
    first_execution_id = uuid4()
    report = _run(
        tenant_target,
        migration_set,
        execution_id=first_execution_id,
    )

    assert report.service_identity == TENANT_SERVICE.identity
    assert report.provisioning_spec_digest == TENANT_PROVISIONING_SPEC.digest
    assert report.migration_set_digest == migration_set.digest
    assert report.database_name == TENANT_PROVISIONING_SPEC.database_name
    assert report.system_identifier.isdigit()
    assert report.server_version_num == SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM
    assert report.previous_version == 0
    assert report.final_version == 1
    assert report.applied_versions == (1,)
    assert report.execution_id == first_execution_id
    assert report.observed_head_execution_id == first_execution_id
    assert report.verified_noop is False
    assert _relation_exists(tenant_target, "ofarm.migration_runner_probe")
    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        assert connection.execute(
            "SELECT pg_catalog.to_regprocedure("
            "'ofarm_infrastructure.seal_tenant_routine_owners()') IS NULL"
        ).fetchone() == (True,)
        sealer = TENANT_PROVISIONING_SPEC.tenant_initial_owner_sealer
        assert sealer is not None
        transfer_names = sorted(
            {transfer.function_name for transfer in sealer.transfers}
        )
        assert connection.execute(
            """
            SELECT routine.proname::text,
                   pg_catalog.pg_get_function_identity_arguments(routine.oid),
                   owner.rolname::text
            FROM pg_catalog.pg_proc AS routine
            JOIN pg_catalog.pg_namespace AS namespace
                 ON namespace.oid = routine.pronamespace
            JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
            WHERE namespace.nspname = 'ofarm'
              AND routine.proname = ANY (%s::text[])
            ORDER BY 1, 2
            """,
            (transfer_names,),
        ).fetchall() == sorted(
            (
                transfer.function_name,
                transfer.identity_arguments,
                transfer.owner_role,
            )
            for transfer in sealer.transfers
        )
    assert _ledger_rows(tenant_target) == [
        (
            1,
            "0001_initial.sql",
            migration_set.migrations[0].source_sha256,
            migration_set.migrations[0].byte_length,
            migration_set.prefix_digest(1),
            TENANT_SERVICE.identity,
            TENANT_PROVISIONING_SPEC.digest,
            RELEASE_IDENTITY,
            str(first_execution_id),
        )
    ]

    def _noop_must_not_use_write_commit(*_args, **_kwargs):
        raise AssertionError("verified no-op used the migration commit path")

    monkeypatch.setattr(
        migration_runner_module,
        "_commit",
        _noop_must_not_use_write_commit,
    )
    second_execution_id = uuid4()
    noop = _run(
        tenant_target,
        migration_set,
        execution_id=second_execution_id,
    )
    assert noop.previous_version == noop.final_version == 1
    assert noop.applied_versions == ()
    assert noop.execution_id == second_execution_id
    assert noop.observed_head_execution_id == first_execution_id
    assert noop.verified_noop is True
    assert _ledger_rows(tenant_target)[0][-1] == str(first_execution_id)
    for mutation in (
        "UPDATE ofarm.schema_migration SET release_identity = 'changed'",
        "DELETE FROM ofarm.schema_migration",
        "TRUNCATE TABLE ofarm.schema_migration",
    ):
        with psycopg.connect(
            tenant_target.target_admin_dsn,
            autocommit=True,
        ) as connection:
            with pytest.raises(
                psycopg.errors.ObjectNotInPrerequisiteState,
                match="append-only",
            ):
                connection.execute(mutation)
    assert len(_ledger_rows(tenant_target)) == 1


def test_commit_phase_interrupt_has_an_explicit_unknown_outcome(tmp_path: Path):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": b"SELECT 1;"},
    )
    migration = migration_set.migrations[0]
    execution_id = uuid4()

    class InterruptedCommit:
        def commit(self):
            raise KeyboardInterrupt

    with pytest.raises(MigrationOutcomeUnknown) as raised:
        migration_runner_module._commit(
            InterruptedCommit(),
            migration,
            execution_id,
        )

    assert raised.value.execution_id == execution_id
    assert raised.value.version == 1


def test_tenant_v1_transition_connection_loss_has_an_explicit_unknown_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = Path(__file__).resolve().parents[2]
    current_set = load_migration_set(package_root, TENANT_SERVICE)
    execution_id = uuid4()

    def observe(_admin_dsn, spec):
        if spec is TENANT_PROVISIONING_SPEC:
            raise MigrationTargetError("current infrastructure is absent")
        assert spec is TENANT_PROVISIONING_SPEC_V1
        return object()

    def lose_connection(*_args, **_kwargs):
        raise psycopg.OperationalError(
            "SECRET-TRANSITION-CONNECTION-SENTINEL"
        )

    monkeypatch.setattr(
        migration_runner_module,
        "_observe_infrastructure",
        observe,
    )
    monkeypatch.setattr(
        migration_runner_module,
        "_require_transitionable_tenant_v1",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        migration_runner_module,
        "transition_tenant_service_v1_to_v2",
        lose_connection,
    )

    with pytest.raises(
        MigrationInfrastructureTransitionOutcomeUnknown
    ) as raised:
        migration_runner_module._observe_or_transition_infrastructure(
            admin_dsn="admin-route",
            migrator_dsn="migrator-route",
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=current_set,
            execution_id=execution_id,
            transition_login_passwords={
                "ofarm_identity_resolver": "resolver-password"
            },
        )

    assert isinstance(raised.value, MigrationError)
    assert raised.value.execution_id == execution_id
    assert "SECRET-TRANSITION" not in str(raised.value)


def test_tenant_v1_transition_database_rejection_is_a_closed_migration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = Path(__file__).resolve().parents[2]
    current_set = load_migration_set(package_root, TENANT_SERVICE)

    def observe(_admin_dsn, spec):
        if spec is TENANT_PROVISIONING_SPEC:
            raise MigrationTargetError("current infrastructure is absent")
        assert spec is TENANT_PROVISIONING_SPEC_V1
        return object()

    def reject_transition(*_args, **_kwargs):
        raise psycopg.DatabaseError("SECRET-TRANSITION-DATABASE-SENTINEL")

    monkeypatch.setattr(
        migration_runner_module,
        "_observe_infrastructure",
        observe,
    )
    monkeypatch.setattr(
        migration_runner_module,
        "_require_transitionable_tenant_v1",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        migration_runner_module,
        "transition_tenant_service_v1_to_v2",
        reject_transition,
    )

    with pytest.raises(MigrationTargetError) as raised:
        migration_runner_module._observe_or_transition_infrastructure(
            admin_dsn="admin-route",
            migrator_dsn="migrator-route",
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=current_set,
            execution_id=uuid4(),
            transition_login_passwords={
                "ofarm_identity_resolver": "resolver-password"
            },
        )

    assert isinstance(raised.value, MigrationError)
    assert str(raised.value) == (
        "tenant v1-to-v2 infrastructure transition was rejected"
    )
    assert "SECRET-TRANSITION" not in str(raised.value)


def test_resumes_at_0002_and_preserves_the_stable_0001_prefix(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    initial_source = _initial_source()
    first_set = _load_synthetic_set(
        tmp_path / "first-release",
        {"0001_initial.sql": initial_source},
    )
    full_set = _load_synthetic_set(
        tmp_path / "second-release",
        {
            "0001_initial.sql": initial_source,
            "0002_add_resume_probe.sql": b"""
                CREATE TABLE ofarm.migration_resume_probe (
                    probe_id pg_catalog.int4 PRIMARY KEY
                );
            """,
        },
    )
    _run(tenant_target, first_set)

    report = _run(tenant_target, full_set)

    assert report.previous_version == 1
    assert report.final_version == 2
    assert report.applied_versions == (2,)
    assert _relation_exists(tenant_target, "ofarm.migration_resume_probe")
    rows = _ledger_rows(tenant_target)
    assert [row[0] for row in rows] == [1, 2]
    assert rows[0][4] == first_set.digest == full_set.prefix_digest(1)
    assert rows[1][4] == full_set.digest


def test_accepted_authoritative_v1_upgrades_to_the_current_head(
    tenant_v1_target: _TenantTarget,
    tmp_path: Path,
):
    package_root = Path(__file__).resolve().parents[2]
    current_set = load_migration_set(package_root, TENANT_SERVICE)
    accepted_v1 = _load_synthetic_set(
        tmp_path / "accepted-v1",
        {"0001_initial.sql": current_set.migrations[0].source_bytes},
    )

    assert set(tenant_v1_target.passwords) == set(
        TENANT_PROVISIONING_SPEC_V1.required_password_role_names
    )
    first_report = _run(
        tenant_v1_target,
        accepted_v1,
        spec=TENANT_PROVISIONING_SPEC_V1,
    )
    resolver_password = (
        "accepted-v2-resolver-" + secrets.token_urlsafe(48)
    )
    upgrade_report = migrate_authoritative_service(
        admin_dsn=tenant_v1_target.admin_dsn,
        migrator_dsn=tenant_v1_target.migrator_dsn,
        spec=TENANT_PROVISIONING_SPEC,
        migration_set=current_set,
        release_identity=RELEASE_IDENTITY,
        execution_id=uuid4(),
        transition_login_passwords={
            "ofarm_identity_resolver": resolver_password,
        },
    )

    assert accepted_v1.migrations[0].source_sha256 == (
        "sha256:a51e8144cf1f6c6f553755062ed618c02e23d3749e8355cf33bdb8db4cea633d"
    )
    assert accepted_v1.digest == current_set.prefix_digest(1)
    assert first_report.applied_versions == (1,)
    assert upgrade_report.previous_version == 1
    assert upgrade_report.final_version == 2
    assert upgrade_report.applied_versions == (2,)
    verify_service_infrastructure(
        tenant_v1_target.admin_dsn,
        TENANT_PROVISIONING_SPEC,
    )
    rows = _ledger_rows(tenant_v1_target)
    assert [row[0] for row in rows] == [1, 2]
    assert rows[0][4] == current_set.prefix_digest(1)
    assert rows[1][4] == current_set.digest
    assert rows[0][6] == TENANT_PROVISIONING_SPEC_V1.digest
    assert rows[1][6] == TENANT_PROVISIONING_SPEC.digest


def test_tenant_v1_infrastructure_transition_is_failure_atomic_and_retryable(
    tenant_v1_target: _TenantTarget,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = Path(__file__).resolve().parents[2]
    current_set = load_migration_set(package_root, TENANT_SERVICE)
    accepted_v1 = _load_synthetic_set(
        tmp_path / "accepted-v1",
        {"0001_initial.sql": current_set.migrations[0].source_bytes},
    )
    _run(
        tenant_v1_target,
        accepted_v1,
        spec=TENANT_PROVISIONING_SPEC_V1,
    )
    resolver_password = (
        "atomic-v2-resolver-" + secrets.token_urlsafe(48)
    )
    original_create_membership = provisioning_module._create_membership

    def fail_after_membership(connection, membership) -> None:
        original_create_membership(connection, membership)
        raise RuntimeError("injected tenant-v2 transition failure")

    with monkeypatch.context() as transition_failure:
        transition_failure.setattr(
            provisioning_module,
            "_create_membership",
            fail_after_membership,
        )
        with pytest.raises(
            RuntimeError,
            match="injected tenant-v2 transition failure",
        ):
            migrate_authoritative_service(
                admin_dsn=tenant_v1_target.admin_dsn,
                migrator_dsn=tenant_v1_target.migrator_dsn,
                spec=TENANT_PROVISIONING_SPEC,
                migration_set=current_set,
                release_identity=RELEASE_IDENTITY,
                execution_id=uuid4(),
                transition_login_passwords={
                    "ofarm_identity_resolver": resolver_password,
                },
            )

    verify_service_infrastructure(
        tenant_v1_target.admin_dsn,
        TENANT_PROVISIONING_SPEC_V1,
    )
    retry = migrate_authoritative_service(
        admin_dsn=tenant_v1_target.admin_dsn,
        migrator_dsn=tenant_v1_target.migrator_dsn,
        spec=TENANT_PROVISIONING_SPEC,
        migration_set=current_set,
        release_identity=RELEASE_IDENTITY,
        execution_id=uuid4(),
        transition_login_passwords={
            "ofarm_identity_resolver": resolver_password,
        },
    )
    assert retry.previous_version == 1
    assert retry.final_version == 2
    verify_service_infrastructure(
        tenant_v1_target.admin_dsn,
        TENANT_PROVISIONING_SPEC,
    )


def test_failed_ddl_and_ledger_append_roll_back_together(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    initial_source = _initial_source()
    first_set = _load_synthetic_set(
        tmp_path / "initial",
        {"0001_initial.sql": initial_source},
    )
    failing_set = _load_synthetic_set(
        tmp_path / "failing",
        {
            "0001_initial.sql": initial_source,
            "0002_fail_after_ddl.sql": b"""
                CREATE TABLE ofarm.must_roll_back (
                    probe_id pg_catalog.int4 PRIMARY KEY
                );
                SELECT 1 / 0;
            """,
        },
    )
    _run(tenant_target, first_set)

    with pytest.raises(MigrationExecutionError) as raised:
        _run(tenant_target, failing_set)

    assert raised.value.version == 2
    assert raised.value.filename == "0002_fail_after_ddl.sql"
    assert _relation_exists(tenant_target, "ofarm.must_roll_back") is False
    assert [row[0] for row in _ledger_rows(tenant_target)] == [1]


def test_missing_tenant_sealer_targets_roll_back_ledger_and_keep_capsule(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {
            "0001_initial.sql": initial_ledger_sql(
                TENANT_PROVISIONING_SPEC
            ).encode("utf-8")
        },
    )

    with pytest.raises(MigrationExecutionError, match="does not exist"):
        _run(tenant_target, migration_set)

    assert _relation_exists(tenant_target, "ofarm.schema_migration") is False
    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        assert connection.execute(
            "SELECT pg_catalog.to_regprocedure("
            "'ofarm_infrastructure.seal_tenant_routine_owners()') IS NOT NULL"
        ).fetchone() == (True,)
        assert connection.execute(
            "SELECT pg_catalog.has_schema_privilege("
            "'ofarm_binder', 'ofarm', 'CREATE'), "
            "pg_catalog.has_schema_privilege("
            "'ofarm_tenant_lock_owner', 'ofarm', 'CREATE'), "
            "pg_catalog.has_schema_privilege("
            "'ofarm_migrator', 'ofarm_infrastructure', 'CREATE')"
        ).fetchone() == (False, False, False)


def test_post_sealer_boundary_failure_rolls_every_owner_change_back(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {
            "0001_initial.sql": _initial_source()
            + b"\nGRANT CREATE ON SCHEMA ofarm TO ofarm_app;\n"
        },
    )

    with pytest.raises(MigrationDirtyError, match="widened"):
        _run(tenant_target, migration_set)

    assert _relation_exists(tenant_target, "ofarm.schema_migration") is False
    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        assert connection.execute(
            "SELECT pg_catalog.to_regprocedure("
            "'ofarm.create_tenant_challenge()') IS NULL, "
            "pg_catalog.to_regprocedure("
            "'ofarm.current_tenant_id()') IS NULL, "
            "pg_catalog.to_regprocedure("
            "'ofarm.take_tenant_write_lock()') IS NULL"
        ).fetchone() == (True, True, True)
        assert connection.execute(
            """
            SELECT owner.rolsuper,
                   routine.prosecdef
            FROM pg_catalog.pg_proc AS routine
            JOIN pg_catalog.pg_namespace AS namespace
                 ON namespace.oid = routine.pronamespace
            JOIN pg_catalog.pg_roles AS owner ON owner.oid = routine.proowner
            WHERE namespace.nspname = 'ofarm_infrastructure'
              AND routine.proname = 'seal_tenant_routine_owners'
              AND pg_catalog.pg_get_function_identity_arguments(routine.oid) = ''
            """
        ).fetchone() == (True, True)
        assert connection.execute(
            "SELECT pg_catalog.has_schema_privilege("
            "'ofarm_app', 'ofarm', 'CREATE'), "
            "pg_catalog.has_schema_privilege("
            "'ofarm_binder', 'ofarm', 'CREATE'), "
            "pg_catalog.has_schema_privilege("
            "'ofarm_tenant_lock_owner', 'ofarm', 'CREATE'), "
            "pg_catalog.has_schema_privilege("
            "'ofarm_migrator', 'ofarm_infrastructure', 'CREATE')"
        ).fetchone() == (False, False, False, False)


def test_migration_cannot_change_runner_transaction_posture(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {
            "0001_initial.sql": _initial_source()
            + b"\nSELECT pg_catalog.set_config("
            + b"'synchronous_commit', 'off', true);\n"
        },
    )

    with pytest.raises(MigrationDirtyError, match="widened"):
        _run(tenant_target, migration_set)

    assert _relation_exists(tenant_target, TENANT_SERVICE.qualified_ledger) is False
    assert _relation_exists(tenant_target, "ofarm.migration_runner_probe") is False


def test_fresh_target_with_a_rogue_object_refuses_without_adoption(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        connection.execute(
            "CREATE TABLE ofarm.rogue_before_ledger "
            "(probe_id pg_catalog.int4 PRIMARY KEY)"
        )

    with pytest.raises(MigrationDirtyError):
        _run(tenant_target, migration_set)

    assert _relation_exists(tenant_target, "ofarm.rogue_before_ledger")
    assert _relation_exists(tenant_target, TENANT_SERVICE.qualified_ledger) is False


def test_fake_ledger_cannot_become_migration_phase_evidence(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        connection.execute(
            "CREATE TABLE ofarm.schema_migration "
            "(version pg_catalog.int4 PRIMARY KEY)"
        )

    with pytest.raises(ProvisioningDriftError, match="infrastructure"):
        verify_service_infrastructure(
            tenant_target.admin_dsn,
            TENANT_PROVISIONING_SPEC,
        )
    with pytest.raises(MigrationTargetError, match="infrastructure"):
        _run(tenant_target, migration_set)

    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        columns = connection.execute(
            """
            SELECT attribute.attname::text
            FROM pg_catalog.pg_attribute AS attribute
            WHERE attribute.attrelid =
                  'ofarm.schema_migration'::pg_catalog.regclass
              AND attribute.attnum > 0
              AND NOT attribute.attisdropped
            ORDER BY attribute.attnum
            """
        ).fetchall()
    assert columns == [("version",)]


@pytest.mark.parametrize(
    "drift_sql",
    (
        "ALTER ROLE ofarm_app IN DATABASE ofarm_tenant "
        "SET statement_timeout = '31000'",
        "ALTER DEFAULT PRIVILEGES FOR ROLE ofarm_owner "
        "GRANT EXECUTE ON FUNCTIONS TO PUBLIC",
        "GRANT EXECUTE ON FUNCTION "
        "pg_catalog.pg_advisory_xact_lock(pg_catalog.int8) TO ofarm_app",
    ),
)
def test_locked_runner_discards_clean_but_stale_admin_observation(
    tenant_target: _TenantTarget,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift_sql: str,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    real_observer = migration_runner_module.verify_service_infrastructure

    def observe_then_drift(admin_dsn: str, spec: ProvisioningSpec):
        report = real_observer(admin_dsn, spec)
        with psycopg.connect(
            tenant_target.target_admin_dsn,
            autocommit=True,
        ) as connection:
            connection.execute(drift_sql)
        return report

    monkeypatch.setattr(
        migration_runner_module,
        "verify_service_infrastructure",
        observe_then_drift,
    )

    with pytest.raises(MigrationDirtyError, match="locked provisioning"):
        _run(tenant_target, migration_set)

    assert _relation_exists(tenant_target, TENANT_SERVICE.qualified_ledger) is False
    assert _relation_exists(tenant_target, "ofarm.migration_runner_probe") is False


@pytest.mark.parametrize(
    ("column", "tampered_value", "drop_fixed_constraint"),
    (
        ("source_sha256", "sha256:" + "0" * 64, False),
        ("applied_prefix_digest", "sha256:" + "1" * 64, False),
        ("service_identity", "ofarm.crossed-postgresql.v1", True),
        ("provisioning_spec_digest", "sha256:" + "2" * 64, True),
    ),
)
def test_tampered_history_refuses_without_repair(
    tenant_target: _TenantTarget,
    tmp_path: Path,
    column: str,
    tampered_value: str,
    drop_fixed_constraint: bool,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    _run(tenant_target, migration_set)
    _tamper_ledger_value(
        tenant_target,
        column,
        tampered_value,
        drop_fixed_constraint=drop_fixed_constraint,
    )

    with pytest.raises(MigrationDirtyError):
        _run(tenant_target, migration_set)

    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        observed = connection.execute(
            sql.SQL(
                "SELECT {}::text FROM ofarm.schema_migration WHERE version = 1"
            ).format(sql.Identifier(column))
        ).fetchone()[0]
    assert observed == tampered_value


@pytest.mark.parametrize(
    "constraint_name",
    (
        "schema_migration_version_check",
        "schema_migration_filename_check",
        "schema_migration_source_sha256_check",
        "schema_migration_source_length_check",
        "schema_migration_prefix_digest_check",
        "schema_migration_service_check",
        "schema_migration_provisioning_digest_check",
        "schema_migration_release_check",
        "schema_migration_execution_id_check",
        "schema_migration_applied_at_check",
    ),
)
def test_same_named_weakened_ledger_check_refuses(
    tenant_target: _TenantTarget,
    tmp_path: Path,
    constraint_name: str,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    _run(tenant_target, migration_set)
    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        connection.execute(
            sql.SQL(
                "ALTER TABLE ofarm.schema_migration DROP CONSTRAINT {}"
            ).format(sql.Identifier(constraint_name))
        )
        connection.execute(
            sql.SQL(
                "ALTER TABLE ofarm.schema_migration "
                "ADD CONSTRAINT {} CHECK (true)"
            ).format(sql.Identifier(constraint_name))
        )

    with pytest.raises(MigrationDirtyError, match="constraints differ"):
        _run(tenant_target, migration_set)


def test_same_named_ledger_trigger_with_false_predicate_refuses(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    _run(tenant_target, migration_set)
    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        connection.execute(
            "DROP TRIGGER schema_migration_reject_update_delete "
            "ON ofarm.schema_migration"
        )
        connection.execute(
            "UPDATE ofarm.schema_migration "
            "SET release_identity = 'hostile-but-valid' WHERE version = 1"
        )
        connection.execute(
            """
            CREATE TRIGGER schema_migration_reject_update_delete
            BEFORE UPDATE OR DELETE ON ofarm.schema_migration
            FOR EACH ROW WHEN (false)
            EXECUTE FUNCTION ofarm.reject_schema_migration_mutation()
            """
        )

    with pytest.raises(MigrationDirtyError, match="triggers differ"):
        _run(tenant_target, migration_set)


def test_create_then_drop_ledger_rule_restores_verified_noop(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    first = _run(tenant_target, migration_set)
    with psycopg.connect(
        tenant_target.target_admin_dsn,
        autocommit=True,
    ) as connection:
        connection.execute(
            "CREATE RULE migration_rule_probe AS ON INSERT "
            "TO ofarm.schema_migration DO ALSO NOTHING"
        )

    with pytest.raises(MigrationDirtyError, match="relation posture differs"):
        _run(tenant_target, migration_set)

    with psycopg.connect(
        tenant_target.target_admin_dsn,
        autocommit=True,
    ) as connection:
        connection.execute(
            "DROP RULE migration_rule_probe ON ofarm.schema_migration"
        )
        assert connection.execute(
            """
            SELECT relation.relhasrules,
                   EXISTS (
                       SELECT 1
                       FROM pg_catalog.pg_rewrite AS relation_rule
                       WHERE relation_rule.ev_class = relation.oid
                   )
            FROM pg_catalog.pg_class AS relation
            WHERE relation.oid = 'ofarm.schema_migration'::pg_catalog.regclass
            """
        ).fetchone() == (True, False)

    report = _run(tenant_target, migration_set)
    assert report.applied_versions == ()
    assert report.verified_noop is True
    assert report.observed_head_execution_id == first.observed_head_execution_id


@pytest.mark.parametrize(
    ("statements", "expected"),
    (
        (
            (
                "ALTER TABLE ofarm.schema_migration "
                "ADD COLUMN discarded pg_catalog.int4",
                "ALTER TABLE ofarm.schema_migration DROP COLUMN discarded",
            ),
            "relation posture differs",
        ),
        (
            (
                "ALTER TABLE ofarm.schema_migration SET (fillfactor = 70)",
            ),
            "relation posture differs",
        ),
        (
            ("ALTER TABLE ofarm.schema_migration REPLICA IDENTITY FULL",),
            "relation posture differs",
        ),
        (
            (
                "ALTER INDEX ofarm.schema_migration_filename_key "
                "SET (fillfactor = 70)",
            ),
            "indexes differ",
        ),
    ),
)
def test_ledger_relation_or_index_storage_drift_refuses(
    tenant_target: _TenantTarget,
    tmp_path: Path,
    statements: tuple[str, ...],
    expected: str,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    _run(tenant_target, migration_set)
    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        for statement in statements:
            connection.execute(statement)

    with pytest.raises(MigrationDirtyError, match=expected):
        _run(tenant_target, migration_set)


@pytest.mark.parametrize(
    "trigger_clause",
    (
        "BEFORE UPDATE OF release_identity",
        "BEFORE UPDATE OR DELETE",
    ),
)
def test_ledger_trigger_columns_or_arguments_refuse(
    tenant_target: _TenantTarget,
    tmp_path: Path,
    trigger_clause: str,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    _run(tenant_target, migration_set)
    with psycopg.connect(tenant_target.target_admin_dsn) as connection:
        connection.execute(
            "DROP TRIGGER schema_migration_reject_update_delete "
            "ON ofarm.schema_migration"
        )
        arguments = "" if "UPDATE OF" in trigger_clause else "'ignored'"
        connection.execute(
            f"CREATE TRIGGER schema_migration_reject_update_delete "
            f"{trigger_clause} ON ofarm.schema_migration "
            "FOR EACH ROW EXECUTE FUNCTION "
            f"ofarm.reject_schema_migration_mutation({arguments})"
        )

    with pytest.raises(MigrationDirtyError, match="triggers differ"):
        _run(tenant_target, migration_set)


def test_cross_service_set_is_rejected_before_target_writes(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    crossed_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": b"SELECT 1;"},
        service=SECURITY_AUDIT_SERVICE,
    )

    with pytest.raises(MigrationInputError):
        _run(tenant_target, crossed_set)

    assert _relation_exists(tenant_target, TENANT_SERVICE.qualified_ledger) is False
    assert _relation_exists(tenant_target, "ofarm.migration_runner_probe") is False


def test_audit_service_applies_and_verifies_its_own_independent_history(
    audit_target: _TenantTarget,
    tmp_path: Path,
):
    source = initial_ledger_sql(SECURITY_AUDIT_PROVISIONING_SPEC).encode(
        "utf-8"
    ) + b"""
CREATE TABLE ofarm_security.audit_runner_probe (
    probe_id pg_catalog.int4 PRIMARY KEY
);
"""
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": source},
        service=SECURITY_AUDIT_SERVICE,
    )

    report = _run(
        audit_target,
        migration_set,
        spec=SECURITY_AUDIT_PROVISIONING_SPEC,
    )
    noop = _run(
        audit_target,
        migration_set,
        spec=SECURITY_AUDIT_PROVISIONING_SPEC,
    )

    assert report.service_identity == SECURITY_AUDIT_SERVICE.identity
    assert report.provisioning_spec_digest == \
        SECURITY_AUDIT_PROVISIONING_SPEC.digest
    assert report.previous_version == 0
    assert report.applied_versions == (1,)
    assert noop.previous_version == noop.final_version == 1
    assert noop.verified_noop is True
    assert _relation_exists(
        audit_target,
        "ofarm_security.audit_runner_probe",
    )
    with psycopg.connect(audit_target.target_admin_dsn) as connection:
        row = connection.execute(
            """
            SELECT service_identity, provisioning_spec_digest
            FROM ofarm_security.schema_migration
            WHERE version = 1
            """
        ).fetchone()
    assert row == (
        SECURITY_AUDIT_SERVICE.identity,
        SECURITY_AUDIT_PROVISIONING_SPEC.digest,
    )


def test_admin_and_migrator_routes_cannot_be_crossed_between_services(
    tenant_target: _TenantTarget,
    audit_target: _TenantTarget,
    tmp_path: Path,
):
    tenant_set = _load_synthetic_set(
        tmp_path / "tenant",
        {"0001_initial.sql": _initial_source()},
    )
    audit_source = initial_ledger_sql(
        SECURITY_AUDIT_PROVISIONING_SPEC
    ).encode("utf-8") + b"\nSELECT 1;\n"
    audit_set = _load_synthetic_set(
        tmp_path / "audit",
        {"0001_initial.sql": audit_source},
        service=SECURITY_AUDIT_SERVICE,
    )

    with pytest.raises(MigrationTargetError):
        migrate_service(
            admin_dsn=tenant_target.admin_dsn,
            migrator_dsn=audit_target.migrator_dsn,
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=tenant_set,
            release_identity=RELEASE_IDENTITY,
            execution_id=uuid4(),
        )
    with pytest.raises(MigrationTargetError):
        migrate_service(
            admin_dsn=audit_target.admin_dsn,
            migrator_dsn=tenant_target.migrator_dsn,
            spec=SECURITY_AUDIT_PROVISIONING_SPEC,
            migration_set=audit_set,
            release_identity=RELEASE_IDENTITY,
            execution_id=uuid4(),
        )

    assert _relation_exists(
        tenant_target,
        TENANT_SERVICE.qualified_ledger,
    ) is False
    assert _relation_exists(
        audit_target,
        SECURITY_AUDIT_SERVICE.qualified_ledger,
    ) is False


def test_post_migration_infrastructure_verifies_but_fresh_verification_refuses(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source()},
    )
    _run(tenant_target, migration_set)

    infrastructure = verify_service_infrastructure(
        tenant_target.admin_dsn,
        TENANT_PROVISIONING_SPEC,
    )
    assert not hasattr(infrastructure, "migration_ledger_present")
    assert infrastructure.manifest()["migrationPhaseVerified"] is False
    with pytest.raises(ProvisioningDriftError):
        verify_service(tenant_target.admin_dsn, TENANT_PROVISIONING_SPEC)


def test_concurrent_runners_serialize_and_observe_one_committed_history(
    tenant_target: _TenantTarget,
    tmp_path: Path,
):
    migration_set = _load_synthetic_set(
        tmp_path,
        {"0001_initial.sql": _initial_source(delay_seconds=0.35)},
    )

    def run_once() -> MigrationRunReport:
        return _run(tenant_target, migration_set)

    with ThreadPoolExecutor(max_workers=2) as executor:
        reports = list(executor.map(lambda _index: run_once(), range(2)))

    assert sorted(report.applied_versions for report in reports) == [(), (1,)]
    assert sorted(report.previous_version for report in reports) == [0, 1]
    assert all(report.final_version == 1 for report in reports)
    assert len(_ledger_rows(tenant_target)) == 1
