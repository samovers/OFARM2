"""Focused state-machine and command tests for issue #192 store-loss recovery."""

from __future__ import annotations

import inspect
import json
import os
import secrets
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import psycopg.conninfo
import pytest
from psycopg import sql

import deployment.postgresql.security_audit_store_loss as store_loss
import deployment.postgresql.migration_runner as migration_runner_module
import deployment.postgresql.provisioning as provisioning_module
from deployment.postgresql.migration_runner import (
    MigrationRunReport,
    MigrationTargetError,
    _migrate_security_audit_store_loss,
    migrate_service,
)
from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_SERVICE,
    load_authoritative_migration_set,
)
from deployment.postgresql.provisioning import (
    ProvisioningReport,
    ProvisioningTargetError,
    _provision_security_audit_store_loss,
    provision_service,
    verify_service_infrastructure,
)
from deployment.postgresql.provisioning_specs import SECURITY_AUDIT_PROVISIONING_SPEC
from deployment.postgresql.run_security_audit_store_loss import (
    STORE_LOSS_ADMIN_DSN_ENVIRONMENT,
    STORE_LOSS_CONTROL_DSN_ENVIRONMENT,
    STORE_LOSS_MIGRATOR_DSN_ENVIRONMENT,
    STORE_LOSS_PASSWORD_ENVIRONMENTS,
    run_fixed_security_audit_store_loss_cli,
)
from deployment.postgresql.security_audit_store_loss import (
    SecurityAuditStoreLossInputError,
    SecurityAuditStoreLossOutcomeUnknown,
    SecurityAuditStoreLossRefused,
    StoreLossRecoveryReport,
    StoreLossRecoveryRequest,
    StoreLossRecoverySecrets,
)
from deployment.postgresql.version_policy import (
    SUPPORTED_POSTGRESQL_SERVER_VERSION,
    SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
)
from kernel.tests.test_postgresql_physical_clone import (
    POSTGRES_SUPERUSER,
    POSTGRES_SUPERUSER_PASSWORD,
    _docker,
    _dsn,
    _published_port,
    _remove_container,
    _require_exact_pinned_image,
    _system_identifier,
    _wait_for_postgres,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
EXECUTION_ID = UUID("018f0f2a-6a38-7d9b-a4c8-33e9f27b2f6c")
LOSS_START = datetime(2026, 8, 23, 8, 0, tzinfo=timezone.utc)
INTERVAL_END = LOSS_START + timedelta(minutes=5)
OBSERVED_AT = INTERVAL_END + timedelta(microseconds=1)
PURGE_AFTER = OBSERVED_AT + timedelta(days=30)
EVENT_ID = UUID("018f0f2a-6a38-7d9b-a4c8-33e9f27b2f6d")
SYSTEM_IDENTIFIER = "7654321098765432109"


class _Cursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        rows = self.rows
        self.rows = []
        return rows


class _Connection:
    def __init__(self, harness: "_Harness", kind: str) -> None:
        self.harness = harness
        self.kind = kind
        self.closed = False
        self.commands: list[tuple[str, tuple[object, ...] | None]] = []
        self.commit_calls = 0
        self.rollback_calls = 0
        self.close_calls = 0

    def execute(self, query, parameters=None):
        assert type(query) is str
        self.commands.append((query, parameters))
        return self.harness.execute(self, query, parameters)

    def rollback(self) -> None:
        self.rollback_calls += 1

    def commit(self) -> None:
        self.commit_calls += 1
        if self.harness.commit_raises:
            raise OSError("SECRET-COMMIT-CANARY")

    def close(self) -> None:
        self.close_calls += 1
        if self.harness.close_failure == self.kind:
            raise OSError("SECRET-CLOSE-CANARY")
        self.closed = True


class _Harness:
    def __init__(self) -> None:
        self.migration_set = load_authoritative_migration_set(
            PACKAGE_ROOT,
            SECURITY_AUDIT_SERVICE,
        )
        self.connections: list[_Connection] = []
        self.random_calls = 0
        self.provision_calls = 0
        self.migrate_calls = 0
        self.append_calls = 0
        self.created = True
        self.commit_raises = False
        self.final_bad = False
        self.fail_query: str | None = None
        self.lose_witness_at: str | None = None
        self.close_failure: str | None = None

    def random_bytes(self, length: int) -> bytes:
        self.random_calls += 1
        assert length == 16
        return bytes(range(16))

    def connection_factory(self, conninfo: str, *, autocommit: bool):
        index = len(self.connections)
        kind = ("witness", "fresh", "control", "final")[index]
        expected_autocommit = kind != "control"
        assert autocommit is expected_autocommit
        connection = _Connection(self, kind)
        connection.conninfo = conninfo
        self.connections.append(connection)
        return connection

    def provision(self, admin_dsn, *, login_passwords, witness):
        self.provision_calls += 1
        assert set(login_passwords) == set(
            SECURITY_AUDIT_PROVISIONING_SPEC.required_password_role_names
        )
        assert witness.system_identifier == SYSTEM_IDENTIFIER
        return ProvisioningReport(
            service_identity=SECURITY_AUDIT_PROVISIONING_SPEC.identity,
            provisioning_spec_digest=SECURITY_AUDIT_PROVISIONING_SPEC.digest,
            database_name=SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
            system_identifier=SYSTEM_IDENTIFIER,
            server_version_num=SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
            created=self.created,
            migration_ledger_present=False,
        )

    def migrate(
        self,
        *,
        admin_dsn,
        migrator_dsn,
        migration_set,
        release_identity,
        execution_id,
        witness,
    ):
        self.migrate_calls += 1
        assert migration_set is self.migration_set
        assert witness.system_identifier == SYSTEM_IDENTIFIER
        versions = tuple(item.version for item in migration_set.migrations)
        return MigrationRunReport(
            service_identity=SECURITY_AUDIT_SERVICE.identity,
            provisioning_spec_digest=SECURITY_AUDIT_PROVISIONING_SPEC.digest,
            migration_set_digest=migration_set.digest,
            database_name=SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
            system_identifier=SYSTEM_IDENTIFIER,
            server_version_num=SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
            previous_version=0,
            final_version=len(versions),
            applied_versions=versions,
            execution_id=execution_id,
            observed_head_execution_id=execution_id,
        )

    def ledger_rows(self) -> list[tuple[object, ...]]:
        return [
            (
                migration.version,
                migration.filename,
                migration.source_sha256,
                migration.byte_length,
                self.migration_set.prefix_digest(migration.version),
                SECURITY_AUDIT_SERVICE.identity,
                SECURITY_AUDIT_PROVISIONING_SPEC.digest,
                "ofarm-tests/store-loss",
                EXECUTION_ID,
                LOSS_START + timedelta(seconds=migration.version),
            )
            for migration in self.migration_set.migrations
        ]

    def admission_row(self, kind: str) -> tuple[object, ...]:
        if kind == "control":
            user, read_only, isolation = (
                "ofarm_security_audit_control_login",
                "off",
                "read committed",
            )
        else:
            user, read_only, isolation = "ofarm", "on", "repeatable read"
        counts = (0, 0, 0) if self.lose_witness_at == kind else (2, 1, 1)
        return (
            user,
            user,
            SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
            SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
            SUPPORTED_POSTGRESQL_SERVER_VERSION,
            SYSTEM_IDENTIFIER,
            False,
            read_only,
            isolation,
            "on",
            *counts,
        )

    def final_row(self) -> tuple[object, ...]:
        if self.final_bad:
            return (0,) + (None,) * 21
        return (
            1,
            EVENT_ID,
            OBSERVED_AT,
            PURGE_AFTER,
            "AUDIT_GAP",
            "SECURITY_OPERATIONS_V1",
            "AUDIT_CONTROL",
            LOSS_START,
            INTERVAL_END,
            None,
            True,
            "OFARM_PRETENANT_SECURITY_EVENT_V1",
            "CORRELATION_HMAC_ONLY_V1",
            "SECURITY_DIAGNOSTIC_30D_V1",
            32,
            True,
            0,
            0,
            512,
            0,
            0,
            False,
        )

    def execute(self, connection, query, parameters):
        if query == self.fail_query:
            raise OSError("SECRET-STATEMENT-CANARY")
        if query == store_loss.WITNESS_IDENTITY_SQL:
            return _Cursor([(
                "ofarm", "ofarm", "postgres", 5, True,
                SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
                SUPPORTED_POSTGRESQL_SERVER_VERSION,
                SYSTEM_IDENTIFIER, False, "off", 451,
            )])
        if query in (
            store_loss.WITNESS_BIGINT_LOCK_SQL,
            store_loss.WITNESS_INTEGER_PAIR_LOCK_SQL,
        ):
            return _Cursor([(True,)])
        if "WITH witness_locks AS" in query:
            return _Cursor([self.admission_row(connection.kind)])
        if query.startswith("BEGIN TRANSACTION"):
            return _Cursor([])
        if query == store_loss.FRESH_STATE_SQL:
            return _Cursor([store_loss._EXPECTED_FRESH_STATE])
        if query == store_loss.LEDGER_SQL:
            return _Cursor(self.ledger_rows())
        if query == store_loss.CLOCK_SQL:
            return _Cursor([(INTERVAL_END,)])
        if query == store_loss.APPEND_GAP_SQL:
            self.append_calls += 1
            return _Cursor([(EVENT_ID, OBSERVED_AT, PURGE_AFTER)])
        if query == store_loss.FINAL_STATE_SQL:
            return _Cursor([self.final_row()])
        raise AssertionError(f"unexpected fixed SQL: {query[:80]}")

    def dependencies(self):
        return store_loss._Dependencies(
            connection_factory=self.connection_factory,
            random_bytes=self.random_bytes,
            provision=self.provision,
            migrate=self.migrate,
            load_migrations=lambda: self.migration_set,
        )


def _request() -> StoreLossRecoveryRequest:
    return StoreLossRecoveryRequest(
        loss_start=LOSS_START,
        release_identity="ofarm-tests/store-loss",
        execution_id=EXECUTION_ID,
    )


def _secrets() -> StoreLossRecoverySecrets:
    roles = SECURITY_AUDIT_PROVISIONING_SPEC.required_password_role_names
    return StoreLossRecoverySecrets(
        admin_dsn=(
            "host=admin.example dbname=caller_selected user=ofarm "
            "connect_timeout=99 options='-c statement_timeout=999999'"
        ),
        migrator_dsn="host=migrator.example user=ofarm_migrator",
        control_dsn=(
            "host=control.example user=ofarm_security_audit_control_login"
        ),
        login_passwords=tuple(
            (role, f"password-{index}-" + "x" * 32)
            for index, role in enumerate(roles)
        ),
    )


def _run(harness: _Harness) -> StoreLossRecoveryReport:
    return store_loss._run_security_audit_store_loss_for_testing(
        _request(),
        _secrets(),
        harness.dependencies(),
    )


def test_success_holds_one_witness_and_emits_one_exact_report() -> None:
    harness = _Harness()
    report = _run(harness)

    assert harness.random_calls == 1
    assert harness.provision_calls == harness.migrate_calls == 1
    assert harness.append_calls == 1
    assert [connection.kind for connection in harness.connections] == [
        "witness", "fresh", "control", "final"
    ]
    assert len(harness.connections[0].commands) == 3
    assert all(connection.closed for connection in harness.connections)
    document = json.loads(report.report_bytes)
    assert document == {
        "countUnknown": True,
        "eventId": str(EVENT_ID),
        "intervalEnd": "2026-08-23T08:05:00.000000Z",
        "intervalStart": "2026-08-23T08:00:00.000000Z",
        "migrationExecutionId": str(EXECUTION_ID),
        "migrationSetDigest": harness.migration_set.digest,
        "observedAt": "2026-08-23T08:05:00.000001Z",
        "outcome": "RECOVERED",
        "provisioningSpecDigest": SECURITY_AUDIT_PROVISIONING_SPEC.digest,
        "purgeAfter": "2026-09-22T08:05:00.000001Z",
        "schema": store_loss.STORE_LOSS_REPORT_SCHEMA,
        "serviceIdentity": SECURITY_AUDIT_SERVICE.identity,
        "systemIdentifier": SYSTEM_IDENTIFIER,
    }


def test_every_supplied_dsn_replaces_database_timeouts_and_options() -> None:
    harness = _Harness()
    _run(harness)

    parsed = [
        psycopg.conninfo.conninfo_to_dict(connection.conninfo)
        for connection in harness.connections
    ]
    assert [item["dbname"] for item in parsed] == [
        "postgres", "ofarm_security_audit", "ofarm_security_audit",
        "ofarm_security_audit",
    ]
    assert all(item["connect_timeout"] == "5" for item in parsed)
    assert "statement_timeout=999999" not in parsed[0]["options"]
    assert "statement_timeout=2000" in parsed[0]["options"]


@pytest.mark.parametrize(
    ("candidate_request", "secret_carrier"),
    (
        (replace(_request(), loss_start=LOSS_START.replace(tzinfo=None)), _secrets()),
        (replace(_request(), release_identity="contains space"), _secrets()),
        (replace(_request(), execution_id=UUID(int=0)), _secrets()),
        (_request(), replace(_secrets(), admin_dsn="")),
        (_request(), replace(_secrets(), login_passwords=())),
    ),
)
def test_invalid_input_refuses_before_random_or_database_work(
    candidate_request,
    secret_carrier,
) -> None:
    harness = _Harness()
    with pytest.raises(SecurityAuditStoreLossInputError):
        store_loss._run_security_audit_store_loss_for_testing(
            candidate_request,
            secret_carrier,
            harness.dependencies(),
        )
    assert harness.random_calls == 0
    assert harness.connections == []


def test_existing_target_is_not_adopted_or_migrated() -> None:
    harness = _Harness()
    harness.created = False
    with pytest.raises(SecurityAuditStoreLossRefused):
        _run(harness)
    assert harness.provision_calls == 1
    assert harness.migrate_calls == harness.append_calls == 0
    assert [connection.kind for connection in harness.connections] == ["witness"]
    assert harness.connections[0].closed is True


@pytest.mark.parametrize(
    ("stage", "append_calls", "connection_count"),
    (("fresh", 0, 2), ("control", 0, 3), ("final", 1, 4)),
)
def test_lost_or_split_witness_refuses_each_runner_owned_connection(
    stage: str,
    append_calls: int,
    connection_count: int,
) -> None:
    harness = _Harness()
    harness.lose_witness_at = stage
    with pytest.raises(SecurityAuditStoreLossRefused):
        _run(harness)
    assert harness.append_calls == append_calls
    assert len(harness.connections) == connection_count


def test_ambiguous_commit_recovers_only_from_the_one_exact_final_event() -> None:
    harness = _Harness()
    harness.commit_raises = True
    report = _run(harness)
    assert report.event_id == EVENT_ID
    assert harness.append_calls == 1
    assert harness.connections[2].commit_calls == 1


@pytest.mark.parametrize("ambiguous", (False, True))
def test_failed_final_observation_never_retries_the_append(ambiguous: bool) -> None:
    harness = _Harness()
    harness.commit_raises = ambiguous
    harness.final_bad = True
    expected = (
        SecurityAuditStoreLossOutcomeUnknown
        if ambiguous
        else SecurityAuditStoreLossRefused
    )
    with pytest.raises(expected):
        _run(harness)
    assert harness.append_calls == 1
    assert len(harness.connections) == 4


def test_cleanup_failure_withholds_success_after_exact_final_state() -> None:
    harness = _Harness()
    harness.close_failure = "control"
    with pytest.raises(SecurityAuditStoreLossRefused):
        _run(harness)
    assert harness.append_calls == 1
    assert len(harness.connections) == 4


@pytest.mark.parametrize(
    ("failed_query", "append_calls"),
    (
        (store_loss.WITNESS_IDENTITY_SQL, 0),
        (store_loss.FRESH_STATE_SQL, 0),
        (store_loss.CLOCK_SQL, 0),
        (store_loss.APPEND_GAP_SQL, 0),
        (store_loss.FINAL_STATE_SQL, 1),
    ),
    ids=("witness", "fresh", "clock", "append", "final"),
)
def test_database_statement_failures_are_terminal_and_never_retry_append(
    failed_query: str,
    append_calls: int,
) -> None:
    harness = _Harness()
    harness.fail_query = failed_query
    with pytest.raises(SecurityAuditStoreLossRefused) as raised:
        _run(harness)
    assert harness.append_calls == append_calls
    assert "SECRET" not in str(raised.value)


class _Output:
    def __init__(self, *, short: bool = False, flush_failure: bool = False) -> None:
        self.value = b""
        self.short = short
        self.flush_failure = flush_failure

    def write(self, value: bytes) -> int:
        self.value += value
        return len(value) - 1 if self.short else len(value)

    def flush(self) -> None:
        if self.flush_failure:
            raise OSError("SECRET-FLUSH-CANARY")


class _CliRunner:
    def __init__(self, result) -> None:
        self.result = result
        self.calls = 0

    def run(self, request, secret_carrier):
        self.calls += 1
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def _cli_environment() -> dict[str, str]:
    environment = {
        STORE_LOSS_ADMIN_DSN_ENVIRONMENT: "host=admin.example user=ofarm",
        STORE_LOSS_MIGRATOR_DSN_ENVIRONMENT: (
            "host=migrator.example user=ofarm_migrator"
        ),
        STORE_LOSS_CONTROL_DSN_ENVIRONMENT: (
            "host=control.example user=ofarm_security_audit_control_login"
        ),
    }
    environment.update(
        {name: "x" * 40 for _role, name in STORE_LOSS_PASSWORD_ENVIRONMENTS}
    )
    return environment


def _cli_argv() -> tuple[str, ...]:
    return (
        "--loss-start", "2026-08-23T08:00:00.000000Z",
        "--release-identity", "ofarm-tests/store-loss",
        "--execution-id", str(EXECUTION_ID),
    )


def _report() -> StoreLossRecoveryReport:
    return StoreLossRecoveryReport(
        service_identity=SECURITY_AUDIT_SERVICE.identity,
        provisioning_spec_digest=SECURITY_AUDIT_PROVISIONING_SPEC.digest,
        migration_set_digest="sha256:" + "a" * 64,
        system_identifier=SYSTEM_IDENTIFIER,
        migration_execution_id=EXECUTION_ID,
        event_id=EVENT_ID,
        interval_start=LOSS_START,
        interval_end=INTERVAL_END,
        observed_at=OBSERVED_AT,
        purge_after=PURGE_AFTER,
    )


def test_cli_writes_only_the_complete_canonical_report() -> None:
    runner = _CliRunner(_report())
    stdout, stderr = _Output(), _Output()
    exit_code = run_fixed_security_audit_store_loss_cli(
        argv=_cli_argv(), environ=_cli_environment(), stdout=stdout,
        stderr=stderr, runner=runner,
    )
    assert exit_code == 0
    assert stdout.value == _report().report_bytes
    assert stderr.value == b""
    assert runner.calls == 1


@pytest.mark.parametrize(
    ("failure", "exit_code", "prefix"),
    (
        (SecurityAuditStoreLossInputError("SECRET"), 2, b"security-audit"),
        (SecurityAuditStoreLossRefused("SECRET"), 3, b"security-audit"),
        (SecurityAuditStoreLossOutcomeUnknown("SECRET"), 4, b"security-audit"),
        (RuntimeError("SECRET"), 3, b"security-audit"),
    ),
)
def test_cli_failures_are_closed_and_sanitized(failure, exit_code, prefix) -> None:
    stdout, stderr = _Output(), _Output()
    observed = run_fixed_security_audit_store_loss_cli(
        argv=_cli_argv(), environ=_cli_environment(), stdout=stdout,
        stderr=stderr, runner=_CliRunner(failure),
    )
    assert observed == exit_code
    assert stdout.value == b""
    assert stderr.value.startswith(prefix)
    assert b"SECRET" not in stderr.value


@pytest.mark.parametrize("output", (_Output(short=True), _Output(flush_failure=True)))
def test_cli_output_failure_is_never_success(output: _Output) -> None:
    stderr = _Output()
    exit_code = run_fixed_security_audit_store_loss_cli(
        argv=_cli_argv(), environ=_cli_environment(), stdout=output,
        stderr=stderr, runner=_CliRunner(_report()),
    )
    assert exit_code == 5
    assert b"reporting failed" in stderr.value
    assert b"SECRET" not in stderr.value


@pytest.mark.parametrize("stderr", (_Output(short=True), _Output(flush_failure=True)))
def test_cli_diagnostic_failure_preserves_the_closed_exit(stderr: _Output) -> None:
    assert run_fixed_security_audit_store_loss_cli(
        argv=(), environ={}, stdout=_Output(), stderr=stderr,
        runner=_CliRunner(RuntimeError("SECRET")),
    ) == 2


def test_public_owner_apis_and_production_sql_have_no_destructive_surface() -> None:
    assert tuple(inspect.signature(provision_service).parameters) == (
        "admin_dsn", "spec", "login_passwords"
    )
    assert tuple(inspect.signature(verify_service_infrastructure).parameters) == (
        "admin_dsn", "spec"
    )
    sql_values = (
        store_loss.WITNESS_IDENTITY_SQL,
        store_loss.FRESH_STATE_SQL,
        store_loss.LEDGER_SQL,
        store_loss.APPEND_GAP_SQL,
        store_loss.FINAL_STATE_SQL,
    )
    assert not any(
        token in value.upper()
        for value in sql_values
        for token in ("DROP ", "DELETE ", "TRUNCATE ", "COPY ", "RESTORE ")
    )


def _live_admin_dsn() -> str:
    value = os.environ.get(STORE_LOSS_ADMIN_DSN_ENVIRONMENT)
    if value:
        return value
    if os.environ.get("GITHUB_ACTIONS") == "true":
        pytest.fail("the hosted runner is missing the fixed audit admin DSN")
    pytest.skip("a dedicated PostgreSQL 17 audit service is required")


def _database_dsn(
    admin_dsn: str,
    database_name: str,
    user: str,
    password: str,
) -> str:
    parameters = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    parameters.update(dbname=database_name, user=user, password=password)
    return psycopg.conninfo.make_conninfo(**parameters)


def _assert_live_service_absent(admin_dsn: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        database = connection.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            (SECURITY_AUDIT_PROVISIONING_SPEC.database_name,),
        ).fetchone()
        roles = connection.execute(
            r"""
            SELECT rolname::text
            FROM pg_catalog.pg_roles
            WHERE rolname::text LIKE 'ofarm\_%' ESCAPE '\'
            ORDER BY rolname
            """
        ).fetchall()
    assert database is None
    assert roles == []


def _destroy_live_test_service(admin_dsn: str) -> None:
    spec = SECURITY_AUDIT_PROVISIONING_SPEC
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        roles = [
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
        assert roles == sorted(spec.role_names)
        connection.execute(
            """
            SELECT pg_catalog.pg_terminate_backend(pid)
            FROM pg_catalog.pg_stat_activity
            WHERE datname = %s AND pid <> pg_catalog.pg_backend_pid()
            """,
            (spec.database_name,),
        )
        connection.execute(
            sql.SQL("DROP DATABASE {}").format(sql.Identifier(spec.database_name))
        )
        connection.execute(
            sql.SQL("DROP ROLE {}").format(
                sql.SQL(", ").join(sql.Identifier(role) for role in roles)
            )
        )
        for database_name in ("postgres", "template0", "template1"):
            connection.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO PUBLIC").format(
                    sql.Identifier(database_name)
                )
            )
        connection.execute("GRANT TEMPORARY ON DATABASE postgres TO PUBLIC")
        connection.execute(
            "REVOKE TEMPORARY ON DATABASE template0, template1 FROM PUBLIC"
        )


def test_live_recovery_creates_one_gap_and_rerun_is_read_only_refused(
    monkeypatch,
) -> None:
    admin_dsn = _live_admin_dsn()
    _assert_live_service_absent(admin_dsn)
    spec = SECURITY_AUDIT_PROVISIONING_SPEC
    passwords = tuple(
        (
            role,
            f"store-loss-{index}-{secrets.token_urlsafe(32)}",
        )
        for index, role in enumerate(spec.required_password_role_names)
    )
    password_map = dict(passwords)
    secret_carrier = StoreLossRecoverySecrets(
        admin_dsn=admin_dsn,
        migrator_dsn=_database_dsn(
            admin_dsn,
            spec.database_name,
            "ofarm_migrator",
            password_map["ofarm_migrator"],
        ),
        control_dsn=_database_dsn(
            admin_dsn,
            spec.database_name,
            "ofarm_security_audit_control_login",
            password_map["ofarm_security_audit_control_login"],
        ),
        login_passwords=passwords,
    )
    request = StoreLossRecoveryRequest(
        loss_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        release_identity="ofarm-tests/store-loss-live",
        execution_id=UUID("018f0f2a-6a38-7d9b-a4c8-33e9f27b2f6e"),
    )
    witness_admissions: list[tuple[str, str]] = []
    original_assertion = (
        provisioning_module._assert_security_audit_store_loss_witness
    )

    def recording_assertion(connection, witness):
        witness_admissions.append((connection.info.user, connection.info.dbname))
        return original_assertion(connection, witness)

    monkeypatch.setattr(
        provisioning_module,
        "_assert_security_audit_store_loss_witness",
        recording_assertion,
    )
    monkeypatch.setattr(
        migration_runner_module,
        "_assert_security_audit_store_loss_witness",
        recording_assertion,
    )
    monkeypatch.setattr(
        store_loss,
        "_assert_security_audit_store_loss_witness",
        recording_assertion,
    )
    runner = store_loss.SecurityAuditStoreLossRecoveryRunner()
    try:
        report = runner.run(request, secret_carrier)
        assert report.interval_start == request.loss_start
        assert report.interval_end > request.loss_start
        assert witness_admissions == [
            ("ofarm", "postgres"),
            ("ofarm", spec.database_name),
            ("ofarm", spec.database_name),
            ("ofarm", "postgres"),
            ("ofarm", spec.database_name),
            ("ofarm_migrator", spec.database_name),
            ("ofarm", spec.database_name),
            ("ofarm_security_audit_control_login", spec.database_name),
            ("ofarm", spec.database_name),
        ]
        parameters = psycopg.conninfo.conninfo_to_dict(admin_dsn)
        parameters["dbname"] = spec.database_name
        with psycopg.connect(
            psycopg.conninfo.make_conninfo(**parameters),
            autocommit=True,
        ) as connection:
            row = connection.execute(
                """
                SELECT pg_catalog.count(*)::bigint,
                       pg_catalog.min(event_kind)::text,
                       pg_catalog.bool_and(interval_count_unknown)
                FROM ofarm_security.operational_security_event
                """
            ).fetchone()
        assert row == (1, "AUDIT_GAP", True)
        with pytest.raises(SecurityAuditStoreLossRefused):
            runner.run(request, secret_carrier)
        with psycopg.connect(
            psycopg.conninfo.make_conninfo(**parameters),
            autocommit=True,
        ) as connection:
            assert connection.execute(
                "SELECT pg_catalog.count(*) FROM "
                "ofarm_security.operational_security_event"
            ).fetchone() == (1,)
    finally:
        _destroy_live_test_service(admin_dsn)


def _hostile_passwords() -> dict[str, str]:
    return {
        role: f"store-loss-split-{index}-{secrets.token_urlsafe(32)}"
        for index, role in enumerate(
            SECURITY_AUDIT_PROVISIONING_SPEC.required_password_role_names
        )
    }


def _drop_hostile_audit_service(admin_dsn: str, connection_factory) -> None:
    spec = SECURITY_AUDIT_PROVISIONING_SPEC
    with connection_factory(admin_dsn, autocommit=True) as connection:
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
        roles = [
            row[0]
            for row in connection.execute(
                r"""
                SELECT rolname::text FROM pg_catalog.pg_roles
                WHERE rolname::text LIKE 'ofarm\_%' ESCAPE '\'
                ORDER BY rolname
                """
            ).fetchall()
        ]
        if roles:
            assert roles == sorted(spec.role_names)
            connection.execute(
                sql.SQL("DROP ROLE {}").format(
                    sql.SQL(", ").join(sql.Identifier(role) for role in roles)
                )
            )
        for database_name in ("postgres", "template0", "template1"):
            connection.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO PUBLIC").format(
                    sql.Identifier(database_name)
                )
            )
        connection.execute("GRANT TEMPORARY ON DATABASE postgres TO PUBLIC")
        connection.execute(
            "REVOKE TEMPORARY ON DATABASE template0, template1 FROM PUBLIC"
        )


def _hostile_audit_state(admin_dsn: str, connection_factory) -> tuple[object, ...]:
    spec = SECURITY_AUDIT_PROVISIONING_SPEC
    with connection_factory(admin_dsn, autocommit=True) as connection:
        roles = tuple(
            row[0]
            for row in connection.execute(
                r"""
                SELECT rolname::text FROM pg_catalog.pg_roles
                WHERE rolname::text LIKE 'ofarm\_%' ESCAPE '\'
                ORDER BY rolname
                """
            ).fetchall()
        )
        database_exists = connection.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            (spec.database_name,),
        ).fetchone() == (1,)
    if not database_exists:
        return roles, False, (), None, None
    parameters = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    parameters["dbname"] = spec.database_name
    with connection_factory(
        psycopg.conninfo.make_conninfo(**parameters), autocommit=True
    ) as target:
        schemas = tuple(
            row[0]
            for row in target.execute(
                """
                SELECT nspname::text FROM pg_catalog.pg_namespace
                WHERE pg_catalog.left(nspname::text, 3) <> 'pg_'
                  AND nspname <> 'information_schema'
                ORDER BY nspname
                """
            ).fetchall()
        )
        ledger = target.execute(
            "SELECT pg_catalog.to_regclass("
            "'ofarm_security.schema_migration')::pg_catalog.oid"
        ).fetchone()[0]
        event = target.execute(
            "SELECT pg_catalog.to_regclass("
            "'ofarm_security.operational_security_event')::pg_catalog.oid"
        ).fetchone()[0]
        ledger_count = (
            target.execute(
                "SELECT pg_catalog.count(*) FROM ofarm_security.schema_migration"
            ).fetchone()[0]
            if ledger is not None
            else None
        )
        event_count = (
            target.execute(
                "SELECT pg_catalog.count(*) FROM "
                "ofarm_security.operational_security_event"
            ).fetchone()[0]
            if event is not None
            else None
        )
    return roles, True, schemas, ledger_count, event_count


def _route_to_hostile_server(conninfo: str, target_admin_dsn: str) -> str:
    original = psycopg.conninfo.conninfo_to_dict(conninfo)
    target = psycopg.conninfo.conninfo_to_dict(target_admin_dsn)
    for name in ("host", "hostaddr", "port"):
        if name in target:
            original[name] = target[name]
        else:
            original.pop(name, None)
    return psycopg.conninfo.make_conninfo(**original)


class _RecordingLiveConnection:
    def __init__(self, connection) -> None:
        self.connection = connection
        self.commands: list[str] = []

    @property
    def closed(self) -> bool:
        return self.connection.closed

    def execute(self, query, parameters=None):
        self.commands.append(str(query))
        return self.connection.execute(query, parameters)

    def rollback(self) -> None:
        self.connection.rollback()

    def commit(self) -> None:
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()


def test_store_loss_witness_refuses_independent_and_promoted_clone_splits(
    monkeypatch,
) -> None:
    """Every authoritative connection must see A's still-held live locks."""

    postgres_image = _require_exact_pinned_image()
    nonce = uuid4().hex
    names = {
        kind: f"ofarm192-store-loss-{kind}-{nonce}"
        for kind in ("network", "source", "clone", "independent", "basebackup")
    }
    clone_volume = f"ofarm192-store-loss-clone-data-{nonce}"
    real_connect = psycopg.connect
    passwords = _hostile_passwords()
    migration_set = load_authoritative_migration_set(
        PACKAGE_ROOT, SECURITY_AUDIT_SERVICE
    )

    def start_server(name: str) -> tuple[str, int]:
        _docker(
            "run", "--detach", "--name", name,
            "--network", names["network"],
            "--publish", "127.0.0.1::5432",
            "--env", f"POSTGRES_USER={POSTGRES_SUPERUSER}",
            "--env", f"POSTGRES_PASSWORD={POSTGRES_SUPERUSER_PASSWORD}",
            "--env", "POSTGRES_DB=postgres", postgres_image,
        )
        port = _published_port(name)
        dsn = _dsn(
            port, "postgres", POSTGRES_SUPERUSER, POSTGRES_SUPERUSER_PASSWORD
        )
        _wait_for_postgres(dsn, expected_recovery=False)
        return dsn, port

    witness_connection = None
    try:
        _docker("network", "create", names["network"])
        _docker("volume", "create", clone_volume)
        source_admin_dsn, source_port = start_server(names["source"])
        provision_service(
            source_admin_dsn,
            SECURITY_AUDIT_PROVISIONING_SPEC,
            login_passwords=passwords,
        )
        migrate_service(
            admin_dsn=source_admin_dsn,
            migrator_dsn=_dsn(
                source_port,
                SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
                "ofarm_migrator",
                passwords["ofarm_migrator"],
            ),
            spec=SECURITY_AUDIT_PROVISIONING_SPEC,
            migration_set=migration_set,
            release_identity="issue-192-store-loss-clone-template",
            execution_id=uuid4(),
        )
        source_identifier = _system_identifier(source_admin_dsn)
        _docker(
            "run", "--rm", "--name", names["basebackup"],
            "--network", f"container:{names['source']}",
            "--env", f"PGPASSWORD={POSTGRES_SUPERUSER_PASSWORD}",
            "--volume", f"{clone_volume}:/var/lib/postgresql/data",
            "--entrypoint", "/bin/sh", postgres_image, "-ec",
            "chown postgres:postgres /var/lib/postgresql/data && "
            "exec gosu postgres pg_basebackup "
            "--host=127.0.0.1 --port=5432 "
            f"--username={POSTGRES_SUPERUSER} "
            "--pgdata=/var/lib/postgresql/data --checkpoint=fast "
            "--wal-method=stream --write-recovery-conf --no-password",
        )
        _docker(
            "run", "--detach", "--name", names["clone"],
            "--network", names["network"],
            "--publish", "127.0.0.1::5432",
            "--volume", f"{clone_volume}:/var/lib/postgresql/data",
            postgres_image,
        )
        clone_port = _published_port(names["clone"])
        clone_admin_dsn = _dsn(
            clone_port, "postgres", POSTGRES_SUPERUSER,
            POSTGRES_SUPERUSER_PASSWORD,
        )
        _wait_for_postgres(clone_admin_dsn, expected_recovery=True)
        with real_connect(clone_admin_dsn, autocommit=True) as connection:
            assert connection.execute(
                "SELECT pg_catalog.pg_promote(true, 30)"
            ).fetchone() == (True,)
        _wait_for_postgres(clone_admin_dsn, expected_recovery=False)
        assert _system_identifier(clone_admin_dsn) == source_identifier

        independent_admin_dsn, independent_port = start_server(
            names["independent"]
        )
        provision_service(
            independent_admin_dsn,
            SECURITY_AUDIT_PROVISIONING_SPEC,
            login_passwords=passwords,
        )
        migrate_service(
            admin_dsn=independent_admin_dsn,
            migrator_dsn=_dsn(
                independent_port,
                SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
                "ofarm_migrator",
                passwords["ofarm_migrator"],
            ),
            spec=SECURITY_AUDIT_PROVISIONING_SPEC,
            migration_set=migration_set,
            release_identity="issue-192-store-loss-independent",
            execution_id=uuid4(),
        )
        assert _system_identifier(independent_admin_dsn) != source_identifier
        _drop_hostile_audit_service(source_admin_dsn, real_connect)

        parameters = psycopg.conninfo.conninfo_to_dict(source_admin_dsn)
        parameters.update(
            connect_timeout="5", options=store_loss.STORE_LOSS_SHORT_OPTIONS
        )
        witness_connection = real_connect(
            psycopg.conninfo.make_conninfo(**parameters), autocommit=True
        )
        witness = store_loss._witness_carrier(
            witness_connection, bytes(range(16))
        )
        split_targets = (independent_admin_dsn, clone_admin_dsn)

        def split_call(target_dsn, split_index, operation, error_type):
            calls = 0
            before = None

            def routed_connect(conninfo, **kwargs):
                nonlocal calls, before
                calls += 1
                if calls == split_index:
                    before = (
                        _hostile_audit_state(source_admin_dsn, real_connect),
                        _hostile_audit_state(target_dsn, real_connect),
                    )
                    conninfo = _route_to_hostile_server(conninfo, target_dsn)
                return real_connect(conninfo, **kwargs)

            with monkeypatch.context() as patcher:
                patcher.setattr(psycopg, "connect", routed_connect)
                with pytest.raises(error_type, match="store-loss live witness"):
                    operation()
            assert calls == split_index
            assert before is not None
            assert (
                _hostile_audit_state(source_admin_dsn, real_connect),
                _hostile_audit_state(target_dsn, real_connect),
            ) == before

        for target_dsn in split_targets:
            for split_index in (1, 2, 3):
                split_call(
                    target_dsn,
                    split_index,
                    lambda: _provision_security_audit_store_loss(
                        source_admin_dsn,
                        login_passwords=passwords,
                        witness=witness,
                    ),
                    ProvisioningTargetError,
                )
                _drop_hostile_audit_service(source_admin_dsn, real_connect)

        source_provisioning = provision_service(
            source_admin_dsn,
            SECURITY_AUDIT_PROVISIONING_SPEC,
            login_passwords=passwords,
        )
        for target_dsn in split_targets:
            for split_index in (1, 2, 3):
                split_call(
                    target_dsn,
                    split_index,
                    lambda: _migrate_security_audit_store_loss(
                        admin_dsn=source_admin_dsn,
                        migrator_dsn=_dsn(
                            source_port,
                            SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
                            "ofarm_migrator",
                            passwords["ofarm_migrator"],
                        ),
                        migration_set=migration_set,
                        release_identity="issue-192-store-loss-split",
                        execution_id=UUID(
                            "018f0f2a-6a38-7d9b-a4c8-33e9f27b2f70"
                        ),
                        witness=witness,
                    ),
                    MigrationTargetError,
                )
        assert _hostile_audit_state(source_admin_dsn, real_connect)[3] is None

        migration_report = migrate_service(
            admin_dsn=source_admin_dsn,
            migrator_dsn=_dsn(
                source_port,
                SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
                "ofarm_migrator",
                passwords["ofarm_migrator"],
            ),
            spec=SECURITY_AUDIT_PROVISIONING_SPEC,
            migration_set=migration_set,
            release_identity="issue-192-store-loss-runner-stage",
            execution_id=UUID("018f0f2a-6a38-7d9b-a4c8-33e9f27b2f71"),
        )
        request = StoreLossRecoveryRequest(
            loss_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            release_identity="issue-192-store-loss-runner-stage",
            execution_id=migration_report.execution_id,
        )
        secret_carrier = StoreLossRecoverySecrets(
            admin_dsn=source_admin_dsn,
            migrator_dsn=_dsn(
                source_port,
                SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
                "ofarm_migrator",
                passwords["ofarm_migrator"],
            ),
            control_dsn=_dsn(
                source_port,
                SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
                "ofarm_security_audit_control_login",
                passwords["ofarm_security_audit_control_login"],
            ),
            login_passwords=tuple(
                (role, passwords[role])
                for role in SECURITY_AUDIT_PROVISIONING_SPEC.required_password_role_names
            ),
        )
        invocation = store_loss._validated_invocation(request, secret_carrier)
        for target_dsn in split_targets:
            for stage in ("fresh", "control", "final"):
                recordings: list[_RecordingLiveConnection] = []

                def forced_connection(conninfo, *, autocommit):
                    connection = real_connect(
                        _route_to_hostile_server(conninfo, target_dsn),
                        autocommit=autocommit,
                    )
                    recording = _RecordingLiveConnection(connection)
                    recordings.append(recording)
                    return recording

                dependencies = store_loss._Dependencies(
                    connection_factory=forced_connection,
                    random_bytes=lambda _length: b"",
                    provision=lambda *_args, **_kwargs: None,
                    migrate=lambda **_kwargs: None,
                    load_migrations=lambda: migration_set,
                )
                before = (
                    _hostile_audit_state(source_admin_dsn, real_connect),
                    _hostile_audit_state(target_dsn, real_connect),
                )
                with pytest.raises(
                    ProvisioningTargetError, match="store-loss live witness"
                ):
                    if stage == "fresh":
                        store_loss._observe_fresh_state(
                            dependencies, invocation, witness, migration_set
                        )
                    elif stage == "control":
                        store_loss._append_gap(
                            dependencies,
                            invocation,
                            witness,
                            source_provisioning,
                            migration_report,
                        )
                    else:
                        gap = store_loss._GapResult(
                            uuid4(),
                            datetime(2026, 1, 2, tzinfo=timezone.utc),
                            datetime(2026, 1, 2, tzinfo=timezone.utc),
                            datetime(2026, 2, 1, tzinfo=timezone.utc),
                        )
                        store_loss._observe_final_state(
                            dependencies,
                            invocation,
                            witness,
                            migration_set,
                            gap,
                        )
                assert len(recordings) == 1
                statements = recordings[0].commands
                assert len(statements) == 2
                assert "WITH witness_locks AS" in statements[1]
                forbidden = (
                    store_loss.CLOCK_SQL,
                    store_loss.APPEND_GAP_SQL,
                    store_loss.FRESH_STATE_SQL,
                    store_loss.FINAL_STATE_SQL,
                )
                assert all(statement not in statements for statement in forbidden)
                assert (
                    _hostile_audit_state(source_admin_dsn, real_connect),
                    _hostile_audit_state(target_dsn, real_connect),
                ) == before
    finally:
        if witness_connection is not None:
            witness_connection.close()
        for name in ("basebackup", "clone", "independent", "source"):
            _remove_container(names[name])
        _docker("volume", "rm", "--force", clone_volume, check=False)
        _docker("network", "rm", names["network"], check=False)
