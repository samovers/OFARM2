"""Focused evidence for issue #192 process-crash reconciliation."""

from __future__ import annotations

import inspect
import io
import json
import os
import secrets
import signal
import socket
import struct
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event, Thread
from uuid import UUID, uuid4

import psycopg
import psycopg.conninfo
import pytest

import deployment.postgresql.security_audit_process_crash as process_crash
from deployment.postgresql.migration_runner import migrate_service
from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_SERVICE,
    load_authoritative_migration_set,
)
from deployment.postgresql.provisioning import provision_service
from deployment.postgresql.provisioning_specs import (
    SECURITY_AUDIT_PROVISIONING_SPEC,
)
from deployment.postgresql.run_security_audit_process_crash import (
    PROCESS_CRASH_CONTROL_DSN_ENVIRONMENT,
    _TerminalState,
    _freeze_module_status,
    run_fixed_security_audit_process_crash_cli,
)
from deployment.postgresql.security_audit_process_crash import (
    ADMISSION_SQL,
    APPEND_GAP_SQL,
    CLOCK_SQL,
    PROCESS_CRASH_APPLICATION_NAME,
    PROCESS_CRASH_CONNECTION_OPTIONS,
    PROCESS_CRASH_REPORT_BYTES,
    PROCESS_CRASH_REPORT_SCHEMA,
    ProcessCrashReconciliationRequest,
    ProcessCrashReconciliationSecrets,
    SecurityAuditProcessCrashInterrupted,
    SecurityAuditProcessCrashOutcomeUnknown,
    SecurityAuditProcessCrashRefused,
    SecurityAuditProcessCrashReportingFailed,
    reconstruct_process_crash_conninfo,
)
from deployment.postgresql.version_policy import (
    SUPPORTED_POSTGRESQL_SERVER_VERSION,
    SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
)
from kernel.tests.test_postgresql_physical_clone import (
    POSTGRES_SUPERUSER,
    POSTGRES_SUPERUSER_PASSWORD,
    _docker,
    _remove_container,
    _require_exact_pinned_image,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
INTERVAL_START = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
INTERVAL_END = INTERVAL_START + timedelta(seconds=3)
OBSERVED_AT = INTERVAL_END + timedelta(microseconds=1)
PURGE_AFTER = OBSERVED_AT + timedelta(days=30)
EVENT_ID = UUID("018f0f2a-6a38-7d9b-a4c8-33e9f27b2f70")

_INVALID = b"security-audit process-crash reconciliation command is invalid\n"
_REFUSED = (
    b"security-audit process-crash reconciliation was refused; "
    b"no commit succeeded\n"
)
_INTERRUPTED = (
    b"security-audit process-crash reconciliation was interrupted; "
    b"no commit was sent; do not retry automatically\n"
)
_UNKNOWN = (
    b"security-audit process-crash reconciliation outcome is unknown; "
    b"do not retry automatically\n"
)
_REPORT_FAILED = (
    b"security-audit process-crash reconciliation committed but "
    b"reporting failed; do not retry automatically\n"
)


class _DirectInterruption(BaseException):
    pass


class _Cursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class _Connection:
    def __init__(self) -> None:
        self.commands: list[tuple[str, tuple[object, ...] | None]] = []
        self.admission = list(_admission_row())
        self.clock: object = INTERVAL_END
        self.append = [EVENT_ID, OBSERVED_AT, PURGE_AFTER]
        self.fail_query: str | None = None
        self.failure: BaseException = OSError("SECRET-DATABASE-CANARY")
        self.commit_failure: BaseException | None = None
        self.rollback_calls = 0
        self.commit_calls = 0
        self.close_calls = 0
        self.close_failure: BaseException | None = None

    def execute(self, query, parameters=None):
        assert type(query) is str
        self.commands.append((query, parameters))
        if self.fail_query is not None and self.fail_query in query:
            raise self.failure
        if query == ADMISSION_SQL:
            return _Cursor([tuple(self.admission)])
        if query == CLOCK_SQL:
            return _Cursor([(self.clock,)])
        if query == APPEND_GAP_SQL:
            assert parameters == (INTERVAL_START, INTERVAL_END)
            return _Cursor([tuple(self.append)])
        return _Cursor([])

    def commit(self) -> None:
        self.commit_calls += 1
        if self.commit_failure is not None:
            raise self.commit_failure

    def rollback(self) -> None:
        self.rollback_calls += 1

    def close(self) -> None:
        self.close_calls += 1
        if self.close_failure is not None:
            raise self.close_failure


class _Factory:
    def __init__(self, connection: _Connection | None = None) -> None:
        self.connection = connection or _Connection()
        self.calls: list[tuple[str, bool]] = []
        self.failure: BaseException | None = None

    def __call__(self, conninfo: str, *, autocommit: bool):
        self.calls.append((conninfo, autocommit))
        if self.failure is not None:
            raise self.failure
        return self.connection


class _Output:
    def __init__(
        self,
        *,
        short: bool = False,
        write_failure: BaseException | None = None,
        flush_failure: BaseException | None = None,
    ) -> None:
        self.value = bytearray()
        self.short = short
        self.write_failure = write_failure
        self.flush_failure = flush_failure
        self.write_calls = 0
        self.flush_calls = 0

    def write(self, value: bytes) -> int:
        self.write_calls += 1
        if self.write_failure is not None:
            raise self.write_failure
        self.value.extend(value)
        return len(value) - 1 if self.short else len(value)

    def flush(self) -> None:
        self.flush_calls += 1
        if self.flush_failure is not None:
            raise self.flush_failure


class _RunnerFactory:
    def __init__(self, runner) -> None:
        self.runner = runner
        self.failure: BaseException | None = None
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        return self.runner


class _TerminalRunner:
    def __init__(self, value) -> None:
        self.value = value
        self.calls = 0

    def run(self, request, secret_carrier):
        self.calls += 1
        if isinstance(self.value, BaseException):
            raise self.value
        return self.value


def _admission_row() -> tuple[object, ...]:
    return (
        "ofarm_security_audit_control_login",
        "ofarm_security_audit_control_login",
        SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
        SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
        SUPPORTED_POSTGRESQL_SERVER_VERSION,
        False,
        "off",
        "read committed",
        "2s",
        "250ms",
        "10s",
        "15s",
        "UTC",
        "ISO, MDY",
        "on",
    )


def _raw_conninfo(**replacements: str) -> str:
    values = {
        "host": "/tmp/ofarm process crash socket",
        "port": "5432",
        "dbname": SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
        "user": "ofarm_security_audit_control_login",
        "password": "test password with ' quote",
        "sslmode": "disable",
    }
    values.update(replacements)
    return psycopg.conninfo.make_conninfo(**values)


def _secrets(raw: str | None = None) -> ProcessCrashReconciliationSecrets:
    return ProcessCrashReconciliationSecrets(
        reconstruct_process_crash_conninfo(raw or _raw_conninfo())
    )


def _runner(factory: _Factory):
    return process_crash._runner_for_testing(connection_factory=factory)


def _report(factory: _Factory | None = None):
    actual = factory or _Factory()
    return _runner(actual).run(
        ProcessCrashReconciliationRequest(INTERVAL_START),
        _secrets(),
    )


def _argv() -> tuple[str, str]:
    return ("--interval-start", "2026-08-26T12:00:00.000000Z")


def _environ(raw: str | None = None) -> dict[str, str]:
    return {PROCESS_CRASH_CONTROL_DSN_ENVIRONMENT: raw or _raw_conninfo()}


def test_success_uses_one_admitted_transaction_and_exact_report() -> None:
    factory = _Factory()
    report = _report(factory)
    assert len(factory.calls) == 1
    conninfo, autocommit = factory.calls[0]
    assert autocommit is False
    parameters = psycopg.conninfo.conninfo_to_dict(conninfo)
    assert parameters == {
        "application_name": PROCESS_CRASH_APPLICATION_NAME,
        "connect_timeout": "5",
        "dbname": SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
        "gssencmode": "disable",
        "host": "/tmp/ofarm process crash socket",
        "load_balance_hosts": "disable",
        "options": PROCESS_CRASH_CONNECTION_OPTIONS,
        "password": "test password with ' quote",
        "port": "5432",
        "require_auth": "scram-sha-256",
        "sslmode": "disable",
        "target_session_attrs": "read-write",
        "user": "ofarm_security_audit_control_login",
    }
    connection = factory.connection
    assert [query for query, _ in connection.commands] == [
        "BEGIN TRANSACTION ISOLATION LEVEL READ COMMITTED READ WRITE",
        ADMISSION_SQL,
        CLOCK_SQL,
        APPEND_GAP_SQL,
    ]
    assert connection.commit_calls == 1
    assert connection.rollback_calls == 0
    assert connection.close_calls == 1
    assert len(report.report_bytes) == PROCESS_CRASH_REPORT_BYTES == 298
    assert report.report_bytes.endswith(b"\n")
    assert json.loads(report.report_bytes) == {
        "eventId": str(EVENT_ID),
        "intervalEnd": "2026-08-26T12:00:03.000000Z",
        "intervalStart": "2026-08-26T12:00:00.000000Z",
        "observedAt": "2026-08-26T12:00:03.000001Z",
        "purgeAfter": "2026-09-25T12:00:03.000001Z",
        "schema": PROCESS_CRASH_REPORT_SCHEMA,
    }


@pytest.mark.parametrize(
    "raw",
    (
        "postgresql://user:password@localhost/database",
        "host=/tmp/a host=/tmp/b port=5432 dbname=x user=y password=z sslmode=disable",
        "host=/tmp/a port=5432 dbname=x user=y password=z sslmode=disable service=x",
        _raw_conninfo(host="127.0.0.1"),
        _raw_conninfo(host="/tmp/a,/tmp/b"),
        _raw_conninfo(port="0"),
        _raw_conninfo(port="65536"),
        _raw_conninfo(port="٥٤٣٢"),
        _raw_conninfo(dbname="postgres"),
        _raw_conninfo(user="ofarm"),
        _raw_conninfo(sslmode="require"),
    ),
)
def test_closed_conninfo_rejects_every_alternate_authority(raw: str) -> None:
    with pytest.raises(process_crash.SecurityAuditProcessCrashInputError):
        reconstruct_process_crash_conninfo(raw)


def test_conninfo_bounds_and_minimum_libpq_refuse_before_parse_or_connect() -> None:
    with pytest.raises(process_crash.SecurityAuditProcessCrashInputError):
        reconstruct_process_crash_conninfo("x" * 4097)
    with pytest.raises(process_crash.SecurityAuditProcessCrashInputError):
        reconstruct_process_crash_conninfo(
            _raw_conninfo(),
            libpq_version=lambda: 150000,
        )


@pytest.mark.parametrize("index", range(15))
def test_each_database_admission_field_refuses_before_clock(index: int) -> None:
    connection = _Connection()
    connection.admission[index] = None
    with pytest.raises(SecurityAuditProcessCrashRefused):
        _report(_Factory(connection))
    assert [query for query, _ in connection.commands] == [
        "BEGIN TRANSACTION ISOLATION LEVEL READ COMMITTED READ WRITE",
        ADMISSION_SQL,
    ]
    assert connection.rollback_calls == 1
    assert connection.commit_calls == 0


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("clock", INTERVAL_START),
        ("clock", datetime(2026, 8, 26, 12, 0, 3)),
        ("append_event", UUID(int=0)),
        ("append_observed", INTERVAL_END - timedelta(microseconds=1)),
        ("append_purge", PURGE_AFTER + timedelta(microseconds=1)),
    ),
)
def test_invalid_clock_or_append_result_rolls_back_without_retry(
    field: str,
    value: object,
) -> None:
    connection = _Connection()
    if field == "clock":
        connection.clock = value
    elif field == "append_event":
        connection.append[0] = value
    elif field == "append_observed":
        connection.append[1] = value
    else:
        connection.append[2] = value
    with pytest.raises(SecurityAuditProcessCrashRefused):
        _report(_Factory(connection))
    assert connection.rollback_calls == 1
    assert connection.commit_calls == 0


@pytest.mark.parametrize(
    "failure",
    (OSError("SECRET"), KeyboardInterrupt("SECRET"), _DirectInterruption("SECRET")),
)
def test_commit_without_acknowledgement_is_always_unknown(
    failure: BaseException,
) -> None:
    connection = _Connection()
    connection.commit_failure = failure
    with pytest.raises(SecurityAuditProcessCrashOutcomeUnknown):
        _report(_Factory(connection))
    assert connection.commit_calls == 1
    assert connection.rollback_calls == 0
    assert connection.close_calls == 1


def test_typed_idle_timeout_at_commit_is_proven_refusal() -> None:
    connection = _Connection()
    connection.commit_failure = psycopg.errors.IdleInTransactionSessionTimeout(
        "SECRET-IDLE-TIMEOUT-CANARY"
    )
    with pytest.raises(SecurityAuditProcessCrashRefused):
        _report(_Factory(connection))
    assert connection.rollback_calls == 0
    assert connection.close_calls == 1


@pytest.mark.parametrize(
    "failure",
    (KeyboardInterrupt("SECRET"), SystemExit(91), _DirectInterruption("SECRET")),
)
def test_precommit_direct_baseexception_is_fixed_interruption(
    failure: BaseException,
) -> None:
    connection = _Connection()
    connection.fail_query = "clock_timestamp"
    connection.failure = failure
    with pytest.raises(SecurityAuditProcessCrashInterrupted):
        _report(_Factory(connection))
    assert connection.rollback_calls == 1
    assert connection.close_calls == 1


def test_close_failure_after_commit_does_not_revoke_success() -> None:
    connection = _Connection()
    connection.close_failure = _DirectInterruption("SECRET")
    report = _report(_Factory(connection))
    assert report.event_id == EVENT_ID
    assert connection.commit_calls == 1
    assert connection.rollback_calls == 0


def test_report_construction_failure_after_commit_is_fixed(monkeypatch) -> None:
    def fail_report(**_values):
        raise _DirectInterruption("SECRET-REPORT-CANARY")

    monkeypatch.setattr(process_crash, "_render_report", fail_report)
    connection = _Connection()
    with pytest.raises(SecurityAuditProcessCrashReportingFailed):
        _report(_Factory(connection))
    assert connection.commit_calls == 1
    assert connection.rollback_calls == 0


@pytest.mark.parametrize(
    ("value", "status", "diagnostic"),
    (
        (SecurityAuditProcessCrashRefused(), 3, _REFUSED),
        (SecurityAuditProcessCrashInterrupted(), 3, _INTERRUPTED),
        (SecurityAuditProcessCrashOutcomeUnknown(), 4, _UNKNOWN),
        (SecurityAuditProcessCrashReportingFailed(), 5, _REPORT_FAILED),
    ),
)
def test_cli_terminal_classes_have_exact_closed_protocol(
    value: BaseException,
    status: int,
    diagnostic: bytes,
) -> None:
    stdout = _Output()
    stderr = _Output()
    observed = run_fixed_security_audit_process_crash_cli(
        argv=_argv(),
        environ=_environ(),
        stdout=stdout,
        stderr=stderr,
        runner_factory=_RunnerFactory(_TerminalRunner(value)),
    )
    assert observed == status
    assert bytes(stdout.value) == b""
    assert bytes(stderr.value) == diagnostic
    assert stderr.write_calls == stderr.flush_calls == 1


def test_cli_success_writes_and_flushes_exactly_once() -> None:
    report = _report()
    stdout = _Output()
    stderr = _Output()
    state = _TerminalState()
    observed = run_fixed_security_audit_process_crash_cli(
        argv=_argv(),
        environ=_environ(),
        stdout=stdout,
        stderr=stderr,
        runner_factory=_RunnerFactory(_TerminalRunner(report)),
        terminal_state=state,
    )
    assert observed == 0
    assert state == _TerminalState(controlled_status=0, reported=True)
    assert bytes(stdout.value) == report.report_bytes
    assert bytes(stderr.value) == b""
    assert stdout.write_calls == stdout.flush_calls == 1


@pytest.mark.parametrize(
    "stdout",
    (
        _Output(short=True),
        _Output(write_failure=_DirectInterruption("SECRET")),
        _Output(flush_failure=SystemExit(91)),
    ),
)
def test_cli_output_failure_is_reporting_failed_even_if_complete_looking(
    stdout: _Output,
) -> None:
    stderr = _Output()
    observed = run_fixed_security_audit_process_crash_cli(
        argv=_argv(),
        environ=_environ(),
        stdout=stdout,
        stderr=stderr,
        runner_factory=_RunnerFactory(_TerminalRunner(_report())),
    )
    assert observed == 5
    assert bytes(stderr.value) == _REPORT_FAILED
    assert stdout.write_calls == 1
    assert len(stdout.value) in {0, PROCESS_CRASH_REPORT_BYTES}


@pytest.mark.parametrize(
    "stderr",
    (
        _Output(short=True),
        _Output(write_failure=_DirectInterruption("SECRET")),
        _Output(flush_failure=SystemExit(91)),
    ),
)
def test_stderr_failure_preserves_controlled_status(stderr: _Output) -> None:
    observed = run_fixed_security_audit_process_crash_cli(
        argv=(),
        environ={},
        stdout=_Output(),
        stderr=stderr,
    )
    assert observed == 2


@pytest.mark.parametrize(
    "argv",
    (
        (),
        ("--interval-start",),
        ("--wrong", "2026-08-26T12:00:00.000000Z"),
        ("--interval-start", "2026-08-26T12:00:00Z"),
        ("--interval-start", "2026-08-26T12:00:00.000000+00:00"),
        ("--interval-start", "2026-08-26T12:00:00.000000Ｚ"),
        ("--interval-start", "2026-08-26T12:00:00.000000Z", "extra"),
    ),
)
def test_invalid_cli_shape_refuses_before_environment_or_runner(argv) -> None:
    stdout = _Output()
    stderr = _Output()
    factory = _RunnerFactory(_TerminalRunner(_report()))
    observed = run_fixed_security_audit_process_crash_cli(
        argv=argv,
        environ={},
        stdout=stdout,
        stderr=stderr,
        runner_factory=factory,
    )
    assert observed == 2
    assert bytes(stderr.value) == _INVALID
    assert factory.calls == 0


@pytest.mark.parametrize("name", ("PGHOST", "PGPORT", "PGSERVICEFILE"))
def test_ambient_pg_authority_refuses_before_runner(name: str) -> None:
    environ = _environ()
    environ[name] = "SECRET-AMBIENT-CANARY"
    factory = _RunnerFactory(_TerminalRunner(_report()))
    stderr = _Output()
    observed = run_fixed_security_audit_process_crash_cli(
        argv=_argv(),
        environ=environ,
        stdout=_Output(),
        stderr=stderr,
        runner_factory=factory,
    )
    assert observed == 2
    assert bytes(stderr.value) == _INVALID
    assert factory.calls == 0


def test_shared_audit_control_environment_is_not_an_input() -> None:
    environ = _environ()
    environ["OFARM_SECURITY_AUDIT_CONTROL_PG_DSN"] = (
        "host=attacker.invalid port=1 dbname=wrong user=wrong "
        "password=SECRET-SHARED-CANARY sslmode=require"
    )
    report = _report()
    stdout = _Output()
    stderr = _Output()
    observed = run_fixed_security_audit_process_crash_cli(
        argv=_argv(),
        environ=environ,
        stdout=stdout,
        stderr=stderr,
        runner_factory=_RunnerFactory(_TerminalRunner(report)),
    )
    assert observed == 0
    assert bytes(stdout.value) == report.report_bytes
    assert bytes(stderr.value) == b""
    assert b"SECRET-SHARED-CANARY" not in stdout.value


@pytest.mark.parametrize(
    "failure",
    (KeyboardInterrupt("SECRET"), SystemExit(91), _DirectInterruption("SECRET")),
)
def test_runner_construction_interruption_uses_fixed_status(
    failure: BaseException,
) -> None:
    factory = _RunnerFactory(_TerminalRunner(_report()))
    factory.failure = failure
    stderr = _Output()
    observed = run_fixed_security_audit_process_crash_cli(
        argv=_argv(),
        environ=_environ(),
        stdout=_Output(),
        stderr=stderr,
        runner_factory=factory,
    )
    assert observed == 3
    assert bytes(stderr.value) == _INTERRUPTED


def test_module_status_freezing_rejects_caller_selected_systemexit() -> None:
    state = _TerminalState()

    def caller_selected(_state):
        raise SystemExit(91)

    assert _freeze_module_status(caller_selected, state) == 3
    assert state.controlled_status == 3


def test_module_status_freezing_preserves_reported_success() -> None:
    state = _TerminalState(controlled_status=0, reported=True)

    def interrupted(_state):
        raise KeyboardInterrupt("SECRET")

    assert _freeze_module_status(interrupted, state) == 0


def test_actual_module_entry_invalid_input_has_no_python_termination_surface() -> None:
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(PACKAGE_ROOT),
    }
    result = subprocess.run(
        (sys.executable, "-m", "deployment.postgresql.run_security_audit_process_crash"),
        cwd=PACKAGE_ROOT,
        env=environment,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == _INVALID
    assert b"Traceback" not in result.stderr


def test_terminal_architecture_has_one_nonreturning_exit_and_no_systemexit() -> None:
    source = inspect.getsource(
        __import__(
            "deployment.postgresql.run_security_audit_process_crash",
            fromlist=["*"],
        )
    )
    assert source.count("os._exit(controlled_status)") == 1
    assert "raise SystemExit" not in source
    assert "sys.exit" not in source


def test_production_sql_has_only_admission_clock_and_existing_append() -> None:
    sql_values = (ADMISSION_SQL, CLOCK_SQL, APPEND_GAP_SQL)
    forbidden = ("INSERT ", "UPDATE ", "DELETE ", "COPY ", "DROP ", "TRUNCATE ")
    assert not any(
        token in statement.upper()
        for statement in sql_values
        for token in forbidden
    )
    assert APPEND_GAP_SQL.count("append_audit_gap") == 1
    assert "0, true" in APPEND_GAP_SQL


def test_report_flush_is_not_accidentally_supplied_by_unbuffered_python() -> None:
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(PACKAGE_ROOT),
    }
    result = subprocess.run(
        (
            sys.executable,
            "-c",
            "import os,sys;sys.stdout.buffer.write(b'UNFLUSHED');os._exit(0)",
        ),
        cwd=PACKAGE_ROOT,
        env=environment,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == b""


def test_stalled_sink_has_no_false_repository_wall_clock_claim() -> None:
    source = inspect.getsource(process_crash)
    assert "signal.alarm" not in source
    assert "threading" not in source
    assert "asyncio" not in source
    assert "sleep(" not in source
    assert io.DEFAULT_BUFFER_SIZE > 0


@dataclass(frozen=True, slots=True)
class _LiveAudit:
    control_raw_conninfo: str
    reader_conninfo: str
    socket_directory: Path
    port: int


def _socket_dsn(
    socket_directory: Path,
    port: int,
    database: str,
    user: str,
    password: str,
) -> str:
    return psycopg.conninfo.make_conninfo(
        host=str(socket_directory),
        port=str(port),
        dbname=database,
        user=user,
        password=password,
        sslmode="disable",
    )


def _wait_for_socket_postgres(admin_dsn: str) -> None:
    deadline = time.monotonic() + 30
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(
                admin_dsn,
                autocommit=True,
                connect_timeout=1,
            ) as connection:
                assert connection.execute("SELECT 1").fetchone() == (1,)
            return
        except psycopg.Error as error:
            last_error = error
        time.sleep(0.2)
    raise AssertionError("socket-mounted PostgreSQL did not start") from last_error


@pytest.fixture(scope="module")
def live_process_crash_audit(tmp_path_factory) -> _LiveAudit:
    image = _require_exact_pinned_image()
    nonce = uuid4().hex
    container = f"ofarm192-process-crash-{nonce}"
    socket_directory = tmp_path_factory.mktemp("process-crash-pg-socket")
    socket_directory.chmod(0o777)
    port = 5432
    try:
        _docker(
            "run",
            "--detach",
            "--name",
            container,
            "--env",
            f"POSTGRES_USER={POSTGRES_SUPERUSER}",
            "--env",
            f"POSTGRES_PASSWORD={POSTGRES_SUPERUSER_PASSWORD}",
            "--env",
            "POSTGRES_DB=postgres",
            "--env",
            "POSTGRES_INITDB_ARGS=--auth-local=scram-sha-256 "
            "--auth-host=scram-sha-256",
            "--volume",
            f"{socket_directory}:/ofarm-pg-socket",
            image,
            "-c",
            "unix_socket_directories=/var/run/postgresql,/ofarm-pg-socket",
        )
        admin_dsn = _socket_dsn(
            socket_directory,
            port,
            "postgres",
            POSTGRES_SUPERUSER,
            POSTGRES_SUPERUSER_PASSWORD,
        )
        _wait_for_socket_postgres(admin_dsn)
        passwords = {
            role: f"process-crash-{index}-{secrets.token_urlsafe(32)}"
            for index, role in enumerate(
                SECURITY_AUDIT_PROVISIONING_SPEC.required_password_role_names
            )
        }
        provision_service(
            admin_dsn,
            SECURITY_AUDIT_PROVISIONING_SPEC,
            login_passwords=passwords,
        )
        migrate_service(
            admin_dsn=admin_dsn,
            migrator_dsn=_socket_dsn(
                socket_directory,
                port,
                SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
                "ofarm_migrator",
                passwords["ofarm_migrator"],
            ),
            spec=SECURITY_AUDIT_PROVISIONING_SPEC,
            migration_set=load_authoritative_migration_set(
                PACKAGE_ROOT,
                SECURITY_AUDIT_SERVICE,
            ),
            release_identity="issue-192-process-crash-live",
            execution_id=uuid4(),
        )
        yield _LiveAudit(
            control_raw_conninfo=_socket_dsn(
                socket_directory,
                port,
                SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
                "ofarm_security_audit_control_login",
                passwords["ofarm_security_audit_control_login"],
            ),
            reader_conninfo=_socket_dsn(
                socket_directory,
                port,
                SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
                "ofarm_security_audit_reader_login",
                passwords["ofarm_security_audit_reader_login"],
            ),
            socket_directory=socket_directory,
            port=port,
        )
    finally:
        _remove_container(container)


def _live_event_rows(reader_conninfo: str) -> list[tuple[object, ...]]:
    with psycopg.connect(reader_conninfo, autocommit=True) as connection:
        return connection.execute(
            """
            SELECT event_id,
                   event_kind,
                   interval_start,
                   interval_end,
                   interval_event_count,
                   interval_count_unknown,
                   reason,
                   correlation_hmac_value,
                   access_purpose
            FROM ofarm_security.query_operational_security_events(
                NULL, NULL, NULL, 100, 1048576
            )
            ORDER BY observed_at, event_id
            """
        ).fetchall()


def test_live_postgresql_records_one_unknown_count_gap(
    live_process_crash_audit: _LiveAudit,
) -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    report = process_crash.SecurityAuditProcessCrashReconciliationRunner().run(
        ProcessCrashReconciliationRequest(start),
        ProcessCrashReconciliationSecrets(
            reconstruct_process_crash_conninfo(
                live_process_crash_audit.control_raw_conninfo
            )
        ),
    )
    assert report.interval_start == start
    assert report.interval_end > start
    assert report.observed_at >= report.interval_end
    rows = _live_event_rows(live_process_crash_audit.reader_conninfo)
    matching = [row for row in rows if row[0] == report.event_id]
    assert matching == [
        (
            report.event_id,
            "AUDIT_GAP",
            start,
            report.interval_end,
            0,
            True,
            None,
            None,
            None,
        )
    ]


class _AppendBarrierRelay:
    """Hold only the request-bound append completion in an open transaction."""

    _APPEND_MARKER = b"ofarm_security.append_audit_gap"

    def __init__(
        self,
        *,
        relay_directory: Path,
        upstream_directory: Path,
        port: int,
        raw_control_conninfo: str,
    ) -> None:
        self._relay_directory = relay_directory
        self._upstream_path = str(upstream_directory / f".s.PGSQL.{port}")
        self._listener_path = relay_directory / f".s.PGSQL.{port}"
        self._listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._listener.bind(str(self._listener_path))
        self._listener.listen(1)
        self._listener.settimeout(15)
        self._stopped = Event()
        self.barrier = Event()
        self._errors: list[BaseException] = []
        self._client: socket.socket | None = None
        self._upstream: socket.socket | None = None
        self.client_target_messages: list[str] = []
        self.target_statement_name: bytes | None = None
        self.held_server_messages: list[tuple[str, bytes]] = []
        self._thread = Thread(target=self._serve, daemon=True)
        fields = psycopg.conninfo.conninfo_to_dict(raw_control_conninfo)
        fields["host"] = str(relay_directory)
        self.raw_conninfo = psycopg.conninfo.make_conninfo(**fields)

    @staticmethod
    def _cstring(payload: bytes, offset: int) -> tuple[bytes, int]:
        end = payload.find(b"\x00", offset)
        if end < 0:
            raise AssertionError("PostgreSQL cstring is incomplete")
        return payload[offset:end], end + 1

    @staticmethod
    def _frames(buffer: bytes, *, startup: bool) -> tuple[list[bytes], bytes]:
        frames: list[bytes] = []
        while True:
            header = 4 if startup else 5
            if len(buffer) < header:
                break
            if startup:
                size = struct.unpack_from("!I", buffer, 0)[0]
            else:
                size = 1 + struct.unpack_from("!I", buffer, 1)[0]
            if size < header or len(buffer) < size:
                break
            frames.append(buffer[:size])
            buffer = buffer[size:]
            if startup:
                startup = False
        return frames, buffer

    def start(self) -> None:
        self._thread.start()

    def close_upstream(self) -> None:
        self._stopped.set()
        for connection in (self._upstream, self._client):
            if connection is None:
                continue
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                connection.close()
            except OSError:
                pass

    def close(self) -> None:
        self.close_upstream()
        try:
            self._listener.close()
        except OSError:
            pass
        self._thread.join(timeout=10)
        if self._thread.is_alive():
            raise AssertionError("process-crash relay did not stop")
        if self._errors:
            raise AssertionError("process-crash relay failed") from self._errors[0]

    def _inspect_client(self, frame: bytes) -> None:
        kind = frame[:1]
        payload = frame[5:]
        if kind == b"P":
            statement, offset = self._cstring(payload, 0)
            query, _offset = self._cstring(payload, offset)
            if self._APPEND_MARKER in query:
                self.target_statement_name = statement
                self.client_target_messages.append("Parse")
        elif kind == b"B" and self.target_statement_name is not None:
            _portal, offset = self._cstring(payload, 0)
            statement, _offset = self._cstring(payload, offset)
            if statement == self.target_statement_name:
                self.client_target_messages.append("Bind")
        elif kind == b"D" and self.target_statement_name is not None:
            self.client_target_messages.append("Describe")
        elif kind == b"E" and self.target_statement_name is not None:
            self.client_target_messages.append("Execute")
        elif kind == b"S" and self.target_statement_name is not None:
            self.client_target_messages.append("Sync")

    def _serve(self) -> None:
        try:
            self._client, _address = self._listener.accept()
            self._upstream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._upstream.connect(self._upstream_path)
            self._client.settimeout(15)
            self._upstream.settimeout(15)

            def forward_client() -> None:
                buffer = b""
                startup = True
                try:
                    while not self._stopped.is_set():
                        data = self._client.recv(65536)
                        if not data:
                            return
                        buffer += data
                        frames, buffer = self._frames(buffer, startup=startup)
                        if frames and startup:
                            startup = False
                        for frame in frames:
                            if not startup and frame[:1].isalpha():
                                self._inspect_client(frame)
                            self._upstream.sendall(frame)
                except OSError as error:
                    if not self._stopped.is_set():
                        self._errors.append(error)
                finally:
                    self.close_upstream()

            def forward_server() -> None:
                buffer = b""
                holding = False
                try:
                    while not self._stopped.is_set():
                        data = self._upstream.recv(65536)
                        if not data:
                            return
                        buffer += data
                        frames, buffer = self._frames(buffer, startup=False)
                        for frame in frames:
                            kind = frame[:1]
                            payload = frame[5:]
                            target_ready = self.client_target_messages[-5:] == [
                                "Parse",
                                "Bind",
                                "Describe",
                                "Execute",
                                "Sync",
                            ]
                            if (
                                not holding
                                and target_ready
                                and kind == b"C"
                                and payload == b"SELECT 1\x00"
                            ):
                                holding = True
                            if holding:
                                self.held_server_messages.append(
                                    (kind.decode("ascii"), payload)
                                )
                                if kind == b"Z" and payload == b"T":
                                    self.barrier.set()
                                continue
                            self._client.sendall(frame)
                except OSError as error:
                    if not self._stopped.is_set():
                        self._errors.append(error)
                finally:
                    self.close_upstream()

            client_thread = Thread(target=forward_client, daemon=True)
            server_thread = Thread(target=forward_server, daemon=True)
            client_thread.start()
            server_thread.start()
            client_thread.join()
            server_thread.join()
        except OSError as error:
            if not self._stopped.is_set():
                self._errors.append(error)
        finally:
            self._stopped.set()


@pytest.mark.parametrize("termination", (signal.SIGINT, signal.SIGTERM))
def test_live_request_bound_append_rolls_back_on_process_death(
    live_process_crash_audit: _LiveAudit,
    tmp_path: Path,
    termination: signal.Signals,
) -> None:
    before = _live_event_rows(live_process_crash_audit.reader_conninfo)
    relay_directory = tmp_path / f"relay-{termination.name.lower()}"
    relay_directory.mkdir(mode=0o777)
    relay = _AppendBarrierRelay(
        relay_directory=relay_directory,
        upstream_directory=live_process_crash_audit.socket_directory,
        port=live_process_crash_audit.port,
        raw_control_conninfo=live_process_crash_audit.control_raw_conninfo,
    )
    relay.start()
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(PACKAGE_ROOT),
        PROCESS_CRASH_CONTROL_DSN_ENVIRONMENT: relay.raw_conninfo,
    }
    command = subprocess.Popen(
        (
            sys.executable,
            "-m",
            "deployment.postgresql.run_security_audit_process_crash",
            "--interval-start",
            "2026-01-02T00:00:00.000000Z",
        ),
        cwd=PACKAGE_ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert relay.barrier.wait(timeout=15)
        barrier_time = time.monotonic()
        command.send_signal(termination)
        time.sleep(0.05)
        relay.close_upstream()
        assert time.monotonic() - barrier_time < 5
        stdout, stderr = command.communicate(timeout=10)
    finally:
        if command.poll() is None:
            command.kill()
            command.wait(timeout=10)
        relay.close()
    assert relay.target_statement_name == b""
    assert relay.client_target_messages[-5:] == [
        "Parse",
        "Bind",
        "Describe",
        "Execute",
        "Sync",
    ]
    assert relay.held_server_messages[0] == ("C", b"SELECT 1\x00")
    assert relay.held_server_messages[-1] == ("Z", b"T")
    if termination == signal.SIGINT:
        assert command.returncode == 3
        assert stdout == b""
        assert stderr == _INTERRUPTED
    else:
        assert command.returncode == -signal.SIGTERM
        assert stdout == b""
        assert stderr == b""
    assert _live_event_rows(live_process_crash_audit.reader_conninfo) == before


def test_actual_module_entry_sigint_stress_has_only_phase_owned_status() -> None:
    script = """
import os
import sys
import deployment.postgresql.run_security_audit_process_crash as command

def controlled(state):
    sys.stdout.buffer.write(b'R')
    sys.stdout.buffer.flush()
    for _index in range(1000):
        pass
    state.controlled_status = 0
    state.reported = True
    return 0

command.main = lambda *args, _terminal_state=None, **kwargs: controlled(
    _terminal_state
)
command._module_entry()
"""
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(PACKAGE_ROOT),
    }
    observed: set[int] = set()
    for _trial in range(256):
        child = subprocess.Popen(
            (sys.executable, "-c", script),
            cwd=PACKAGE_ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert child.stdout is not None
        assert child.stdout.read(1) == b"R"
        child.send_signal(signal.SIGINT)
        stdout, stderr = child.communicate(timeout=10)
        assert stdout == b""
        assert stderr == b""
        assert child.returncode in {0, 3}
        observed.add(child.returncode)
    assert observed <= {0, 3}
