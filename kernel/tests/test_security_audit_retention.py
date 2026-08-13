"""Focused tests for one-shot security-audit logical retention execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO, StringIO
from pathlib import Path
from time import monotonic
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
import pytest
from psycopg import IsolationLevel
from psycopg.pq import TransactionStatus

from deployment.postgresql.audit_contract import RETENTION_SECONDS
from deployment.postgresql.run_security_audit_retention import (
    RETENTION_DSN_ENVIRONMENT,
    run_fixed_security_audit_retention_cli,
)
from deployment.postgresql.security_audit_retention import (
    AcknowledgedSecurityAuditRetention,
    RETENTION_CONNECTION_OPTIONS,
    RETENTION_CONNECT_TIMEOUT_SECONDS,
    RETENTION_SQL,
    SecurityAuditRetentionOutcomeUnknown,
    SecurityAuditRetentionRefused,
    SecurityAuditRetentionResult,
    SecurityAuditRetentionRunner,
    SecurityAuditRetentionUnavailable,
)
from kernel.tests.postgresql_audit_support import (
    audit_service_fixture,  # noqa: F401
    role_dsn,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
CUTOFF = datetime(2026, 8, 12, 9, 10, 11, 123456, tzinfo=timezone.utc)
OBSERVED_AT = datetime(2026, 8, 12, 9, 10, 11, 234567, tzinfo=timezone.utc)
PURGE_AFTER = OBSERVED_AT + timedelta(seconds=RETENTION_SECONDS)
RETENTION_EVENT_ID = UUID("11111111-1111-4111-8111-111111111111")
EXPECTED_REPORT = (
    b'{"cutoff":"2026-08-12T09:10:11.123456Z","deletedCount":1024,'
    b'"observedAt":"2026-08-12T09:10:11.234567Z",'
    b'"outcome":"ACKNOWLEDGED",'
    b'"purgeAfter":"2026-09-11T09:10:11.234567Z",'
    b'"retentionEventId":"11111111-1111-4111-8111-111111111111"}\n'
)


def _valid_row() -> tuple[object, ...]:
    return (
        CUTOFF,
        1024,
        RETENTION_EVENT_ID,
        OBSERVED_AT,
        PURGE_AFTER,
    )


@dataclass
class _FakeInfo:
    transaction_status: TransactionStatus = TransactionStatus.IDLE


class _FakeCursor:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def fetchone(self) -> object:
        if not self._rows:
            return None
        return self._rows.pop(0)


class _FakeConnection:
    def __init__(
        self,
        rows: list[object] | None = None,
        *,
        closed: bool = False,
        autocommit: bool = False,
        transaction_status: TransactionStatus = TransactionStatus.IDLE,
        execute_error: Exception | None = None,
        commit_error: BaseException | None = None,
        close_error: Exception | None = None,
        isolation_error: Exception | None = None,
    ) -> None:
        self.closed = closed
        self.autocommit = autocommit
        self.info = _FakeInfo(transaction_status)
        self._isolation_level: IsolationLevel | None = None
        self._isolation_error = isolation_error
        self._rows = list([_valid_row()] if rows is None else rows)
        self._execute_error = execute_error
        self._commit_error = commit_error
        self._close_error = close_error
        self.executed: list[str] = []
        self.rollback_calls = 0
        self.commit_calls = 0
        self.close_calls = 0

    @property
    def isolation_level(self) -> IsolationLevel | None:
        return self._isolation_level

    @isolation_level.setter
    def isolation_level(self, value: IsolationLevel | None) -> None:
        if self._isolation_error is not None:
            raise self._isolation_error
        self._isolation_level = value

    def execute(self, query: str) -> _FakeCursor:
        self.executed.append(query)
        if self._execute_error is not None:
            raise self._execute_error
        return _FakeCursor(self._rows)

    def rollback(self) -> None:
        self.rollback_calls += 1

    def commit(self) -> None:
        self.commit_calls += 1
        if self._commit_error is not None:
            raise self._commit_error

    def close(self) -> None:
        self.close_calls += 1
        self.closed = True
        if self._close_error is not None:
            raise self._close_error


class _FakeFactory:
    def __init__(
        self,
        connection: _FakeConnection | None = None,
        error: Exception | None = None,
    ) -> None:
        self.connection = connection
        self.error = error
        self.calls: list[tuple[str, bool, int, str]] = []

    def __call__(
        self,
        conninfo: str,
        *,
        autocommit: bool,
        connect_timeout: int,
        options: str,
    ) -> _FakeConnection:
        self.calls.append((conninfo, autocommit, connect_timeout, options))
        if self.error is not None:
            raise self.error
        assert self.connection is not None
        return self.connection


class _StubRunner:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.calls: list[str] = []

    def run(self, conninfo: str) -> AcknowledgedSecurityAuditRetention:
        self.calls.append(conninfo)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        assert isinstance(self.outcome, AcknowledgedSecurityAuditRetention)
        return self.outcome


class _RecordingOutput:
    def __init__(
        self,
        *,
        short_write: bool = False,
        write_error: Exception | None = None,
        flush_error: Exception | None = None,
    ) -> None:
        self.short_write = short_write
        self.write_error = write_error
        self.flush_error = flush_error
        self.value = bytearray()
        self.flush_calls = 0

    def write(self, value: bytes) -> int:
        if self.write_error is not None:
            raise self.write_error
        count = len(value) - 1 if self.short_write else len(value)
        self.value.extend(value[:count])
        return count

    def flush(self) -> None:
        self.flush_calls += 1
        if self.flush_error is not None:
            raise self.flush_error


def _acknowledged(report: bytes = EXPECTED_REPORT) -> AcknowledgedSecurityAuditRetention:
    return AcknowledgedSecurityAuditRetention(
        result=SecurityAuditRetentionResult(
            cutoff=CUTOFF,
            deleted_count=1024,
            retention_event_id=RETENTION_EVENT_ID,
            observed_at=OBSERVED_AT,
            purge_after=PURGE_AFTER,
        ),
        report_bytes=report,
    )


def _run_cli(
    runner: _StubRunner,
    *,
    argv: tuple[str, ...] = (),
    environ: dict[str, str] | None = None,
    stdout: _RecordingOutput | BytesIO | None = None,
) -> tuple[int, _RecordingOutput | BytesIO, StringIO]:
    output = stdout or BytesIO()
    error = StringIO()
    code = run_fixed_security_audit_retention_cli(
        argv=argv,
        environ=(
            {RETENTION_DSN_ENVIRONMENT: "host=audit dbname=ofarm_security_audit"}
            if environ is None
            else environ
        ),
        stdout=output,
        stderr=error,
        runner=runner,
    )
    return code, output, error


def test_runner_submits_one_fixed_transaction_and_renders_exact_report():
    connection = _FakeConnection()
    factory = _FakeFactory(connection)
    acknowledged = SecurityAuditRetentionRunner(factory).run(
        "host=audit connect_timeout=0 options='-c statement_timeout=0'"
    )

    assert factory.calls == [
        (
            "host=audit connect_timeout=0 options='-c statement_timeout=0'",
            False,
            RETENTION_CONNECT_TIMEOUT_SECONDS,
            RETENTION_CONNECTION_OPTIONS,
        )
    ]
    assert connection.executed == [RETENTION_SQL]
    assert connection.isolation_level == IsolationLevel.READ_COMMITTED
    assert connection.rollback_calls == 0
    assert connection.commit_calls == 1
    assert connection.close_calls == 1
    assert acknowledged.result == SecurityAuditRetentionResult(
        cutoff=CUTOFF,
        deleted_count=1024,
        retention_event_id=RETENTION_EVENT_ID,
        observed_at=OBSERVED_AT,
        purge_after=PURGE_AFTER,
    )
    assert acknowledged.report_bytes == EXPECTED_REPORT


def test_runner_normalizes_timezone_aware_values_to_six_digit_utc():
    east = timezone(timedelta(hours=2))
    cutoff = CUTOFF.astimezone(east)
    observed_at = OBSERVED_AT.astimezone(east)
    purge_after = PURGE_AFTER.astimezone(east)
    connection = _FakeConnection(
        [(cutoff, 1024, RETENTION_EVENT_ID, observed_at, purge_after)]
    )

    acknowledged = SecurityAuditRetentionRunner(_FakeFactory(connection)).run(
        "host=audit"
    )

    assert acknowledged.result.cutoff == CUTOFF
    assert acknowledged.result.observed_at == OBSERVED_AT
    assert acknowledged.result.purge_after == PURGE_AFTER
    assert acknowledged.report_bytes == EXPECTED_REPORT


@pytest.mark.parametrize(
    ("purge_shift", "accepted"),
    (
        pytest.param(timedelta(0), True, id="exact-duration"),
        pytest.param(
            timedelta(microseconds=1),
            False,
            id="one-microsecond-late",
        ),
    ),
)
def test_runner_validates_elapsed_duration_across_zoneinfo_transition(
    purge_shift: timedelta,
    accepted: bool,
):
    zone = ZoneInfo("Europe/Belgrade")
    observed_at = datetime(2026, 3, 15, 12, tzinfo=zone)
    normalized_observed_at = observed_at.astimezone(timezone.utc)
    purge_after = (
        normalized_observed_at
        + timedelta(seconds=RETENTION_SECONDS)
        + purge_shift
    ).astimezone(zone)
    normalized_purge_after = purge_after.astimezone(timezone.utc)
    cutoff = normalized_observed_at - timedelta(seconds=RETENTION_SECONDS)
    connection = _FakeConnection(
        [(cutoff, 1024, RETENTION_EVENT_ID, observed_at, purge_after)]
    )
    factory = _FakeFactory(connection)
    runner = SecurityAuditRetentionRunner(factory)

    assert observed_at.utcoffset() == timedelta(hours=1)
    assert purge_after.utcoffset() == timedelta(hours=2)

    if accepted:
        acknowledged = runner.run("host=audit")

        assert acknowledged.result == SecurityAuditRetentionResult(
            cutoff=cutoff,
            deleted_count=1024,
            retention_event_id=RETENTION_EVENT_ID,
            observed_at=normalized_observed_at,
            purge_after=normalized_purge_after,
        )
        assert acknowledged.report_bytes == (
            b'{"cutoff":"2026-02-13T11:00:00.000000Z","deletedCount":1024,'
            b'"observedAt":"2026-03-15T11:00:00.000000Z",'
            b'"outcome":"ACKNOWLEDGED",'
            b'"purgeAfter":"2026-04-14T11:00:00.000000Z",'
            b'"retentionEventId":"11111111-1111-4111-8111-111111111111"}\n'
        )
        assert connection.rollback_calls == 0
        assert connection.commit_calls == 1
    else:
        with pytest.raises(SecurityAuditRetentionRefused):
            runner.run("host=audit")

        assert connection.rollback_calls == 1
        assert connection.commit_calls == 0

    assert len(factory.calls) == 1
    assert connection.executed == [RETENTION_SQL]
    assert connection.close_calls == 1


def test_connection_failure_is_unavailable_and_never_retried():
    factory = _FakeFactory(error=psycopg.OperationalError("secret-host"))

    with pytest.raises(SecurityAuditRetentionUnavailable):
        SecurityAuditRetentionRunner(factory).run("host=secret-host")

    assert len(factory.calls) == 1


@pytest.mark.parametrize(
    ("closed", "autocommit", "status"),
    (
        pytest.param(True, False, TransactionStatus.IDLE, id="closed"),
        pytest.param(False, True, TransactionStatus.IDLE, id="autocommit"),
        pytest.param(False, False, TransactionStatus.INTRANS, id="in-transaction"),
    ),
)
def test_invalid_returned_connection_state_refuses_before_sql_or_commit(
    closed: bool,
    autocommit: bool,
    status: TransactionStatus,
):
    connection = _FakeConnection(
        closed=closed,
        autocommit=autocommit,
        transaction_status=status,
    )

    with pytest.raises(SecurityAuditRetentionRefused):
        SecurityAuditRetentionRunner(_FakeFactory(connection)).run("host=audit")

    assert connection.executed == []
    assert connection.rollback_calls == 0
    assert connection.commit_calls == 0
    assert connection.close_calls == 1


def test_isolation_failure_refuses_before_sql_or_commit():
    connection = _FakeConnection(isolation_error=RuntimeError("canary"))

    with pytest.raises(SecurityAuditRetentionRefused):
        SecurityAuditRetentionRunner(_FakeFactory(connection)).run("host=audit")

    assert connection.executed == []
    assert connection.commit_calls == 0
    assert connection.close_calls == 1


def test_transport_loss_before_submission_is_unavailable_without_sql_or_commit():
    connection = _FakeConnection(
        isolation_error=psycopg.OperationalError("transport canary")
    )

    with pytest.raises(SecurityAuditRetentionUnavailable):
        SecurityAuditRetentionRunner(_FakeFactory(connection)).run("host=audit")

    assert connection.executed == []
    assert connection.rollback_calls == 0
    assert connection.commit_calls == 0
    assert connection.close_calls == 1


def test_transport_loss_after_submission_is_unavailable_without_commit():
    connection = _FakeConnection(
        execute_error=psycopg.OperationalError("secret transport failure")
    )

    with pytest.raises(SecurityAuditRetentionUnavailable):
        SecurityAuditRetentionRunner(_FakeFactory(connection)).run("host=audit")

    assert connection.executed == [RETENTION_SQL]
    assert connection.rollback_calls == 1
    assert connection.commit_calls == 0
    assert connection.close_calls == 1


def test_deterministic_sql_failure_is_refused_before_commit():
    connection = _FakeConnection(
        execute_error=psycopg.errors.LockNotAvailable("secret database refusal")
    )

    with pytest.raises(SecurityAuditRetentionRefused):
        SecurityAuditRetentionRunner(_FakeFactory(connection)).run("host=audit")

    assert connection.rollback_calls == 1
    assert connection.commit_calls == 0
    assert connection.close_calls == 1


@pytest.mark.parametrize(
    "rows",
    (
        pytest.param([], id="missing-row"),
        pytest.param([list(_valid_row())], id="non-tuple-row"),
        pytest.param([_valid_row()[:-1]], id="short-row"),
        pytest.param([_valid_row(), _valid_row()], id="duplicate-row"),
        pytest.param(
            [
                (
                    CUTOFF.replace(tzinfo=None),
                    1024,
                    RETENTION_EVENT_ID,
                    OBSERVED_AT,
                    PURGE_AFTER,
                )
            ],
            id="naive-cutoff",
        ),
        pytest.param(
            [(CUTOFF, True, RETENTION_EVENT_ID, OBSERVED_AT, PURGE_AFTER)],
            id="boolean-count",
        ),
        pytest.param(
            [(CUTOFF, 1025, RETENTION_EVENT_ID, OBSERVED_AT, PURGE_AFTER)],
            id="oversized-count",
        ),
        pytest.param(
            [(CUTOFF, 1, UUID(int=0), OBSERVED_AT, PURGE_AFTER)],
            id="nil-event-id",
        ),
        pytest.param(
            [
                (
                    CUTOFF,
                    1,
                    RETENTION_EVENT_ID,
                    OBSERVED_AT,
                    PURGE_AFTER + timedelta(microseconds=1),
                )
            ],
            id="inconsistent-purge-after",
        ),
    ),
)
def test_invalid_result_rolls_back_and_never_commits(rows: list[object]):
    connection = _FakeConnection(rows)

    with pytest.raises(SecurityAuditRetentionRefused):
        SecurityAuditRetentionRunner(_FakeFactory(connection)).run("host=audit")

    assert connection.rollback_calls == 1
    assert connection.commit_calls == 0
    assert connection.close_calls == 1


@pytest.mark.parametrize(
    "commit_error",
    (
        pytest.param(
            psycopg.OperationalError("class 08 commit canary"),
            id="operational-error",
        ),
        pytest.param(
            psycopg.DatabaseError("other server commit canary"),
            id="other-server-error",
        ),
    ),
)
def test_every_commit_exception_is_unknown_without_rollback_or_retry(
    commit_error: Exception,
):
    connection = _FakeConnection(commit_error=commit_error)
    factory = _FakeFactory(connection)

    with pytest.raises(SecurityAuditRetentionOutcomeUnknown):
        SecurityAuditRetentionRunner(factory).run("host=audit")

    assert len(factory.calls) == 1
    assert connection.rollback_calls == 0
    assert connection.commit_calls == 1
    assert connection.close_calls == 1


def test_post_commit_close_failure_cannot_downgrade_acknowledgement():
    connection = _FakeConnection(close_error=RuntimeError("close canary"))

    acknowledged = SecurityAuditRetentionRunner(_FakeFactory(connection)).run(
        "host=audit"
    )

    assert connection.commit_calls == 1
    assert connection.close_calls == 1
    assert acknowledged.report_bytes == EXPECTED_REPORT


@pytest.mark.parametrize(
    "argv",
    (
        pytest.param(("-h",), id="short-help"),
        pytest.param(("--help",), id="long-help"),
        pytest.param(("--",), id="separator"),
        pytest.param(("value",), id="positional"),
        pytest.param(("--cutoff", "2026-08-12"), id="cutoff"),
    ),
)
def test_cli_rejects_every_nonempty_argument_shape_without_running(argv):
    runner = _StubRunner(_acknowledged())

    code, output, error = _run_cli(runner, argv=argv)

    assert code == 2
    assert output.getvalue() == b""
    assert error.getvalue() == "security-audit retention command is invalid\n"
    assert runner.calls == []


@pytest.mark.parametrize(
    "environ",
    (
        pytest.param({}, id="missing"),
        pytest.param({RETENTION_DSN_ENVIRONMENT: "   "}, id="whitespace"),
        pytest.param(
            {RETENTION_DSN_ENVIRONMENT: "host='unterminated"},
            id="malformed",
        ),
    ),
)
def test_cli_rejects_invalid_conninfo_without_running(environ):
    runner = _StubRunner(_acknowledged())

    code, output, error = _run_cli(runner, environ=environ)

    assert code == 2
    assert output.getvalue() == b""
    assert error.getvalue() == "security-audit retention command is invalid\n"
    assert runner.calls == []


def test_cli_writes_exact_acknowledged_bytes_and_flushes():
    runner = _StubRunner(_acknowledged())
    output = _RecordingOutput()

    code, returned_output, error = _run_cli(runner, stdout=output)

    assert code == 0
    assert returned_output is output
    assert bytes(output.value) == EXPECTED_REPORT
    assert output.flush_calls == 1
    assert error.getvalue() == ""
    assert runner.calls == ["host=audit dbname=ofarm_security_audit"]


@pytest.mark.parametrize(
    ("outcome", "exit_code", "line"),
    (
        pytest.param(
            SecurityAuditRetentionRefused("secret"),
            1,
            "security-audit retention was refused\n",
            id="refused",
        ),
        pytest.param(
            SecurityAuditRetentionUnavailable("secret"),
            3,
            "security-audit retention is unavailable; no commit was sent\n",
            id="unavailable",
        ),
        pytest.param(
            SecurityAuditRetentionOutcomeUnknown("secret"),
            4,
            "security-audit retention outcome is unknown; "
            "do not retry automatically\n",
            id="unknown",
        ),
        pytest.param(
            RuntimeError("unexpected secret"),
            4,
            "security-audit retention outcome is unknown; "
            "do not retry automatically\n",
            id="unexpected",
        ),
    ),
)
def test_cli_failure_protocol_is_closed_and_never_leaks_details(
    outcome: Exception,
    exit_code: int,
    line: str,
):
    runner = _StubRunner(outcome)

    code, output, error = _run_cli(runner)

    assert code == exit_code
    assert output.getvalue() == b""
    assert error.getvalue() == line
    assert "secret" not in error.getvalue()
    assert len(runner.calls) == 1


@pytest.mark.parametrize(
    ("output", "expected_prefix", "flush_calls"),
    (
        pytest.param(
            _RecordingOutput(short_write=True),
            EXPECTED_REPORT[:-1],
            0,
            id="short-write",
        ),
        pytest.param(
            _RecordingOutput(write_error=OSError("write canary")),
            b"",
            0,
            id="write-error",
        ),
        pytest.param(
            _RecordingOutput(flush_error=OSError("flush canary")),
            EXPECTED_REPORT,
            1,
            id="flush-error",
        ),
    ),
)
def test_cli_reporting_failure_is_exit_five_without_second_database_attempt(
    output: _RecordingOutput,
    expected_prefix: bytes,
    flush_calls: int,
):
    runner = _StubRunner(_acknowledged())

    code, returned_output, error = _run_cli(runner, stdout=output)

    assert code == 5
    assert returned_output is output
    assert bytes(output.value) == expected_prefix
    assert output.flush_calls == flush_calls
    assert error.getvalue() == (
        "security-audit retention committed but reporting failed; "
        "do not retry automatically\n"
    )
    assert len(runner.calls) == 1


def test_operator_documentation_is_one_shot_and_claim_limited():
    documentation = (PACKAGE_ROOT / "deployment/postgresql/README.md").read_text()

    assert "python -m deployment.postgresql.run_security_audit_retention" in documentation
    assert "performs exactly one database-owned logical-retention" in documentation
    assert "batch and accepts no arguments" in documentation
    assert "must not retry exit `4`, exit `5`" in documentation
    assert "This command is not a scheduler or drain loop." in documentation
    assert "physical-erasure claim" in documentation


def _retention_event_count(state: dict[str, object]) -> int:
    with psycopg.connect(str(state["target_admin_dsn"])) as admin:
        return admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm_security.operational_security_event
            WHERE event_kind = 'AUDIT_RETENTION'
            """
        ).fetchone()[0]


def test_live_wrong_role_refuses_without_deletion_or_retention_event(
    migrated_audit_service,
):
    state = migrated_audit_service
    before = _retention_event_count(state)

    with pytest.raises(SecurityAuditRetentionRefused):
        SecurityAuditRetentionRunner().run(
            role_dsn(state, "ofarm_security_audit_reader_login")
        )

    assert _retention_event_count(state) == before


def test_live_early_invocation_acknowledges_zero_deletion_and_matching_event(
    migrated_audit_service,
):
    state = migrated_audit_service
    acknowledged = SecurityAuditRetentionRunner().run(
        role_dsn(state, "ofarm_security_audit_retention_login")
    )

    assert acknowledged.result.deleted_count == 0
    assert acknowledged.result.purge_after == acknowledged.result.observed_at + timedelta(
        seconds=RETENTION_SECONDS
    )
    with psycopg.connect(str(state["target_admin_dsn"])) as admin:
        stored = admin.execute(
            """
            SELECT event_kind, retention_cutoff, retention_deleted_count,
                   observed_at, purge_after
            FROM ofarm_security.operational_security_event
            WHERE event_id = %s
            """,
            (acknowledged.result.retention_event_id,),
        ).fetchone()
    assert stored == (
        "AUDIT_RETENTION",
        acknowledged.result.cutoff,
        0,
        acknowledged.result.observed_at,
        acknowledged.result.purge_after,
    )


def test_live_conflicting_lock_refuses_with_fixed_timeout_and_no_second_attempt(
    migrated_audit_service,
):
    state = migrated_audit_service
    before = _retention_event_count(state)
    with psycopg.connect(str(state["target_admin_dsn"])) as locker:
        locker.execute(
            "LOCK TABLE ofarm_security.operational_security_event "
            "IN ACCESS EXCLUSIVE MODE"
        )
        started_at = monotonic()
        with pytest.raises(SecurityAuditRetentionRefused):
            SecurityAuditRetentionRunner().run(
                role_dsn(state, "ofarm_security_audit_retention_login")
            )
        elapsed = monotonic() - started_at

    assert elapsed < 5
    assert _retention_event_count(state) == before
