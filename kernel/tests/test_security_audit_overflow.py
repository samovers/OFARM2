"""Focused tests for one-shot security-audit overflow closure execution."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from threading import Barrier, Event
from time import monotonic
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
import pytest
from psycopg import IsolationLevel
from psycopg.pq import TransactionStatus

from deployment.postgresql.audit_contract import RETENTION_SECONDS
from deployment.postgresql.run_security_audit_overflow import (
    OVERFLOW_DSN_ENVIRONMENT,
    run_fixed_security_audit_overflow_cli,
)
from deployment.postgresql.security_audit_overflow import (
    CLOSE_OVERFLOW_SQL,
    CompletedSecurityAuditOverflowRun,
    NO_CLOSEABLE_BUCKET_REPORT,
    OBSERVE_OVERFLOW_SQL,
    OVERFLOW_CONNECTION_OPTIONS,
    OVERFLOW_CONNECT_TIMEOUT_SECONDS,
    SecurityAuditOverflowBucket,
    SecurityAuditOverflowClosureResult,
    SecurityAuditOverflowOutcomeUnknown,
    SecurityAuditOverflowRefused,
    SecurityAuditOverflowRunner,
    SecurityAuditOverflowUnavailable,
)
from kernel.tests.postgresql_audit_support import (
    audit_service_fixture,  # noqa: F401
    role_dsn,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
BUCKET_START = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
OBSERVED_AT = datetime(2026, 8, 14, 8, 1, 0, 123456, tzinfo=timezone.utc)
PURGE_AFTER = OBSERVED_AT + timedelta(seconds=RETENTION_SECONDS)
OVERFLOW_ENDED_EVENT_ID = UUID("11111111-1111-4111-8111-111111111111")
EXPECTED_ACKNOWLEDGED_REPORT = (
    b'{"bucketStart":"2026-08-14T08:00:00.000000Z",'
    b'"component":"AUTHENTICATION",'
    b'"observedAt":"2026-08-14T08:01:00.123456Z",'
    b'"outcome":"ACKNOWLEDGED",'
    b'"overflowEndedEventId":"11111111-1111-4111-8111-111111111111",'
    b'"producer":"AUTHENTICATION_BOUNDARY_V1",'
    b'"purgeAfter":"2026-09-13T08:01:00.123456Z",'
    b'"schema":"ofarm.security-audit-overflow-closure-report.v1"}\n'
)
EXPECTED_NO_BUCKET_REPORT = (
    b'{"outcome":"NO_CLOSEABLE_BUCKET",'
    b'"schema":"ofarm.security-audit-overflow-closure-report.v1"}\n'
)


def _valid_observation_row(
    bucket_start: datetime = BUCKET_START,
) -> tuple[object, ...]:
    return (
        "AUTHENTICATION_BOUNDARY_V1",
        "AUTHENTICATION",
        bucket_start,
    )


def _valid_closure_row(
    observed_at: datetime = OBSERVED_AT,
    purge_after: datetime = PURGE_AFTER,
) -> tuple[object, ...]:
    return (
        OVERFLOW_ENDED_EVENT_ID,
        observed_at,
        purge_after,
    )


@dataclass
class _FakeInfo:
    transaction_status: TransactionStatus = TransactionStatus.IDLE


class _FakeCursor:
    def __init__(
        self,
        rows: list[object],
        *,
        fetch_error: BaseException | None = None,
        fetch_error_at: int = 1,
    ) -> None:
        self._rows = rows
        self._fetch_error = fetch_error
        self._fetch_error_at = fetch_error_at
        self.fetchone_calls = 0

    def fetchone(self) -> object:
        self.fetchone_calls += 1
        if (
            self._fetch_error is not None
            and self.fetchone_calls == self._fetch_error_at
        ):
            raise self._fetch_error
        if not self._rows:
            return None
        return self._rows.pop(0)


class _FakeConnection:
    def __init__(
        self,
        observation_rows: list[object] | None = None,
        closure_rows: list[object] | None = None,
        *,
        closed: bool = False,
        autocommit: bool = False,
        transaction_status: TransactionStatus = TransactionStatus.IDLE,
        observation_execute_error: BaseException | None = None,
        close_execute_error: BaseException | None = None,
        observation_fetch_error: BaseException | None = None,
        observation_fetch_error_at: int = 1,
        close_fetch_error: BaseException | None = None,
        close_fetch_error_at: int = 1,
        rollback_error: BaseException | None = None,
        commit_error: BaseException | None = None,
        close_error: Exception | None = None,
        isolation_error: BaseException | None = None,
    ) -> None:
        self.closed = closed
        self.autocommit = autocommit
        self.info = _FakeInfo(transaction_status)
        self._isolation_level: IsolationLevel | None = None
        self._isolation_error = isolation_error
        self._observation_rows = list(
            [_valid_observation_row()]
            if observation_rows is None
            else observation_rows
        )
        self._closure_rows = list(
            [_valid_closure_row()] if closure_rows is None else closure_rows
        )
        self._observation_execute_error = observation_execute_error
        self._close_execute_error = close_execute_error
        self._observation_fetch_error = observation_fetch_error
        self._observation_fetch_error_at = observation_fetch_error_at
        self._close_fetch_error = close_fetch_error
        self._close_fetch_error_at = close_fetch_error_at
        self._rollback_error = rollback_error
        self._commit_error = commit_error
        self._close_error = close_error
        self.executed: list[tuple[str, tuple[object, ...] | None]] = []
        self.cursors: list[_FakeCursor] = []
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

    def execute(
        self,
        query: str,
        parameters: tuple[object, ...] | None = None,
    ) -> _FakeCursor:
        self.executed.append((query, parameters))
        if query == OBSERVE_OVERFLOW_SQL:
            if self._observation_execute_error is not None:
                raise self._observation_execute_error
            cursor = _FakeCursor(
                self._observation_rows,
                fetch_error=self._observation_fetch_error,
                fetch_error_at=self._observation_fetch_error_at,
            )
        elif query == CLOSE_OVERFLOW_SQL:
            if self._close_execute_error is not None:
                raise self._close_execute_error
            cursor = _FakeCursor(
                self._closure_rows,
                fetch_error=self._close_fetch_error,
                fetch_error_at=self._close_fetch_error_at,
            )
        else:
            raise AssertionError("unexpected overflow SQL")
        self.cursors.append(cursor)
        return cursor

    def rollback(self) -> None:
        self.rollback_calls += 1
        if self._rollback_error is not None:
            raise self._rollback_error

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
        error: BaseException | None = None,
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

    def run(self, conninfo: str) -> CompletedSecurityAuditOverflowRun:
        self.calls.append(conninfo)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        assert isinstance(self.outcome, CompletedSecurityAuditOverflowRun)
        return self.outcome


class _RecordingBinaryOutput:
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


def _completed_closure(
    report: bytes = EXPECTED_ACKNOWLEDGED_REPORT,
) -> CompletedSecurityAuditOverflowRun:
    return CompletedSecurityAuditOverflowRun(
        result=SecurityAuditOverflowClosureResult(
            bucket=SecurityAuditOverflowBucket(
                producer="AUTHENTICATION_BOUNDARY_V1",
                component="AUTHENTICATION",
                bucket_start=BUCKET_START,
            ),
            overflow_ended_event_id=OVERFLOW_ENDED_EVENT_ID,
            observed_at=OBSERVED_AT,
            purge_after=PURGE_AFTER,
        ),
        report_bytes=report,
    )


def _completed_no_bucket() -> CompletedSecurityAuditOverflowRun:
    return CompletedSecurityAuditOverflowRun(
        result=None,
        report_bytes=EXPECTED_NO_BUCKET_REPORT,
    )


def _run_cli(
    runner: _StubRunner | SecurityAuditOverflowRunner,
    *,
    argv: tuple[str, ...] = (),
    environ: dict[str, str] | None = None,
    stdout: _RecordingBinaryOutput | BytesIO | None = None,
    stderr: _RecordingBinaryOutput | BytesIO | None = None,
) -> tuple[
    int,
    _RecordingBinaryOutput | BytesIO,
    _RecordingBinaryOutput | BytesIO,
]:
    output = BytesIO() if stdout is None else stdout
    error = BytesIO() if stderr is None else stderr
    code = run_fixed_security_audit_overflow_cli(
        argv=argv,
        environ=(
            {OVERFLOW_DSN_ENVIRONMENT: "host=audit dbname=ofarm_security_audit"}
            if environ is None
            else environ
        ),
        stdout=output,
        stderr=error,
        runner=runner,
    )
    return code, output, error


def test_runner_closes_one_observed_bucket_in_one_transaction():
    connection = _FakeConnection()
    factory = _FakeFactory(connection)

    completed = SecurityAuditOverflowRunner(factory).run(
        "host=audit connect_timeout=0 options='-c statement_timeout=0'"
    )

    assert factory.calls == [
        (
            "host=audit connect_timeout=0 options='-c statement_timeout=0'",
            False,
            OVERFLOW_CONNECT_TIMEOUT_SECONDS,
            OVERFLOW_CONNECTION_OPTIONS,
        )
    ]
    assert connection.executed == [
        (OBSERVE_OVERFLOW_SQL, None),
        (
            CLOSE_OVERFLOW_SQL,
            (
                "AUTHENTICATION_BOUNDARY_V1",
                "AUTHENTICATION",
                BUCKET_START,
            ),
        ),
    ]
    assert connection.isolation_level == IsolationLevel.READ_COMMITTED
    assert connection.rollback_calls == 0
    assert connection.commit_calls == 1
    assert connection.close_calls == 1
    assert completed == _completed_closure()
    assert completed.report_bytes == EXPECTED_ACKNOWLEDGED_REPORT


def test_runner_normalizes_all_aware_timestamps_to_six_digit_utc():
    east = timezone(timedelta(hours=2))
    connection = _FakeConnection(
        observation_rows=[_valid_observation_row(BUCKET_START.astimezone(east))],
        closure_rows=[
            _valid_closure_row(
                OBSERVED_AT.astimezone(east),
                PURGE_AFTER.astimezone(east),
            )
        ],
    )

    completed = SecurityAuditOverflowRunner(_FakeFactory(connection)).run(
        "host=audit"
    )

    assert completed == _completed_closure()
    assert completed.report_bytes == EXPECTED_ACKNOWLEDGED_REPORT


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
def test_runner_validates_elapsed_retention_across_zoneinfo_transition(
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
    connection = _FakeConnection(
        closure_rows=[_valid_closure_row(observed_at, purge_after)]
    )
    runner = SecurityAuditOverflowRunner(_FakeFactory(connection))

    assert observed_at.utcoffset() == timedelta(hours=1)
    assert purge_after.utcoffset() == timedelta(hours=2)

    if accepted:
        completed = runner.run("host=audit")

        assert completed.result is not None
        assert completed.result.observed_at == normalized_observed_at
        assert completed.result.purge_after == purge_after.astimezone(timezone.utc)
        assert connection.commit_calls == 1
    else:
        with pytest.raises(SecurityAuditOverflowRefused):
            runner.run("host=audit")

        assert connection.rollback_calls == 1
        assert connection.commit_calls == 0


def test_no_bucket_rolls_back_without_close_or_commit_and_reports_exact_bytes():
    connection = _FakeConnection(observation_rows=[])

    completed = SecurityAuditOverflowRunner(_FakeFactory(connection)).run(
        "host=audit"
    )

    assert connection.executed == [(OBSERVE_OVERFLOW_SQL, None)]
    assert connection.rollback_calls == 1
    assert connection.commit_calls == 0
    assert connection.close_calls == 1
    assert completed.result is None
    assert completed.report_bytes == EXPECTED_NO_BUCKET_REPORT
    assert completed.report_bytes == NO_CLOSEABLE_BUCKET_REPORT


def test_connection_factory_failure_is_unavailable_and_never_retried():
    factory = _FakeFactory(error=psycopg.OperationalError("secret-host"))

    with pytest.raises(SecurityAuditOverflowUnavailable):
        SecurityAuditOverflowRunner(factory).run("host=secret-host")

    assert len(factory.calls) == 1


@pytest.mark.parametrize(
    ("closed", "autocommit", "status"),
    (
        pytest.param(True, False, TransactionStatus.IDLE, id="closed"),
        pytest.param(False, True, TransactionStatus.IDLE, id="autocommit"),
        pytest.param(False, False, TransactionStatus.INTRANS, id="in-transaction"),
    ),
)
def test_invalid_returned_connection_refuses_before_observation_or_commit(
    closed: bool,
    autocommit: bool,
    status: TransactionStatus,
):
    connection = _FakeConnection(
        closed=closed,
        autocommit=autocommit,
        transaction_status=status,
    )

    with pytest.raises(SecurityAuditOverflowRefused):
        SecurityAuditOverflowRunner(_FakeFactory(connection)).run("host=audit")

    assert connection.executed == []
    assert connection.rollback_calls == 0
    assert connection.commit_calls == 0
    assert connection.close_calls == 1


@pytest.mark.parametrize(
    ("error", "expected"),
    (
        pytest.param(
            RuntimeError("deterministic canary"),
            SecurityAuditOverflowRefused,
            id="deterministic",
        ),
        pytest.param(
            psycopg.OperationalError("transport canary"),
            SecurityAuditOverflowUnavailable,
            id="transport",
        ),
    ),
)
def test_connection_configuration_failure_uses_fixed_transport_split(
    error: Exception,
    expected: type[Exception],
):
    connection = _FakeConnection(isolation_error=error)

    with pytest.raises(expected):
        SecurityAuditOverflowRunner(_FakeFactory(connection)).run("host=audit")

    assert connection.executed == []
    assert connection.commit_calls == 0
    assert connection.close_calls == 1


@pytest.mark.parametrize(
    ("error", "expected"),
    (
        pytest.param(
            psycopg.errors.LockNotAvailable("database refusal"),
            SecurityAuditOverflowRefused,
            id="refused",
        ),
        pytest.param(
            psycopg.OperationalError("transport loss"),
            SecurityAuditOverflowUnavailable,
            id="unavailable",
        ),
    ),
)
def test_observer_execute_failure_uses_fixed_transport_split(
    error: Exception,
    expected: type[Exception],
):
    connection = _FakeConnection(observation_execute_error=error)

    with pytest.raises(expected):
        SecurityAuditOverflowRunner(_FakeFactory(connection)).run("host=audit")

    assert connection.executed == [(OBSERVE_OVERFLOW_SQL, None)]
    assert connection.rollback_calls == 1
    assert connection.commit_calls == 0
    assert connection.close_calls == 1


@pytest.mark.parametrize(
    ("error", "fetch_error_at", "expected"),
    (
        pytest.param(
            psycopg.errors.InvalidParameterValue("fetch refusal"),
            1,
            SecurityAuditOverflowRefused,
            id="first-fetch-refused",
        ),
        pytest.param(
            psycopg.OperationalError("second fetch transport"),
            2,
            SecurityAuditOverflowUnavailable,
            id="second-fetch-unavailable",
        ),
    ),
)
def test_observer_fetch_failure_uses_fixed_transport_split(
    error: Exception,
    fetch_error_at: int,
    expected: type[Exception],
):
    connection = _FakeConnection(
        observation_fetch_error=error,
        observation_fetch_error_at=fetch_error_at,
    )

    with pytest.raises(expected):
        SecurityAuditOverflowRunner(_FakeFactory(connection)).run("host=audit")

    assert connection.executed == [(OBSERVE_OVERFLOW_SQL, None)]
    assert connection.cursors[0].fetchone_calls == fetch_error_at
    assert connection.rollback_calls == 1
    assert connection.commit_calls == 0


@pytest.mark.parametrize(
    "rows",
    (
        pytest.param([None, _valid_observation_row()], id="row-after-empty"),
        pytest.param([list(_valid_observation_row())], id="non-tuple"),
        pytest.param([_valid_observation_row()[:-1]], id="short-row"),
        pytest.param(
            [_valid_observation_row(), _valid_observation_row()],
            id="duplicate-row",
        ),
        pytest.param(
            [("UNKNOWN_PRODUCER", "AUTHENTICATION", BUCKET_START)],
            id="unknown-pair",
        ),
        pytest.param(
            [(1, "AUTHENTICATION", BUCKET_START)],
            id="non-text-producer",
        ),
        pytest.param(
            [_valid_observation_row(BUCKET_START.replace(tzinfo=None))],
            id="naive-bucket",
        ),
        pytest.param(
            [_valid_observation_row(BUCKET_START + timedelta(microseconds=1))],
            id="misaligned-bucket",
        ),
    ),
)
def test_invalid_observation_rolls_back_and_never_closes_or_commits(
    rows: list[object],
):
    connection = _FakeConnection(observation_rows=rows)

    with pytest.raises(SecurityAuditOverflowRefused):
        SecurityAuditOverflowRunner(_FakeFactory(connection)).run("host=audit")

    assert connection.executed == [(OBSERVE_OVERFLOW_SQL, None)]
    assert connection.rollback_calls == 1
    assert connection.commit_calls == 0
    assert connection.close_calls == 1


@pytest.mark.parametrize(
    ("error", "expected"),
    (
        pytest.param(
            psycopg.errors.InvalidParameterValue("close refusal"),
            SecurityAuditOverflowRefused,
            id="refused",
        ),
        pytest.param(
            psycopg.OperationalError("close transport loss"),
            SecurityAuditOverflowUnavailable,
            id="unavailable",
        ),
    ),
)
def test_close_execute_failure_uses_fixed_transport_split(
    error: Exception,
    expected: type[Exception],
):
    connection = _FakeConnection(close_execute_error=error)

    with pytest.raises(expected):
        SecurityAuditOverflowRunner(_FakeFactory(connection)).run("host=audit")

    assert [query for query, _ in connection.executed] == [
        OBSERVE_OVERFLOW_SQL,
        CLOSE_OVERFLOW_SQL,
    ]
    assert connection.rollback_calls == 1
    assert connection.commit_calls == 0
    assert connection.close_calls == 1


@pytest.mark.parametrize(
    ("error", "fetch_error_at", "expected"),
    (
        pytest.param(
            psycopg.errors.InvalidParameterValue("close fetch refusal"),
            1,
            SecurityAuditOverflowRefused,
            id="first-fetch-refused",
        ),
        pytest.param(
            psycopg.OperationalError("close second fetch transport"),
            2,
            SecurityAuditOverflowUnavailable,
            id="second-fetch-unavailable",
        ),
    ),
)
def test_close_fetch_failure_uses_fixed_transport_split(
    error: Exception,
    fetch_error_at: int,
    expected: type[Exception],
):
    connection = _FakeConnection(
        close_fetch_error=error,
        close_fetch_error_at=fetch_error_at,
    )

    with pytest.raises(expected):
        SecurityAuditOverflowRunner(_FakeFactory(connection)).run("host=audit")

    assert connection.cursors[1].fetchone_calls == fetch_error_at
    assert connection.rollback_calls == 1
    assert connection.commit_calls == 0


@pytest.mark.parametrize(
    "rows",
    (
        pytest.param([], id="missing-row"),
        pytest.param([list(_valid_closure_row())], id="non-tuple"),
        pytest.param([_valid_closure_row()[:-1]], id="short-row"),
        pytest.param(
            [_valid_closure_row(), _valid_closure_row()],
            id="duplicate-row",
        ),
        pytest.param(
            [(UUID(int=0), OBSERVED_AT, PURGE_AFTER)],
            id="nil-event-id",
        ),
        pytest.param(
            [("not-a-uuid", OBSERVED_AT, PURGE_AFTER)],
            id="non-uuid-event-id",
        ),
        pytest.param(
            [
                (
                    OVERFLOW_ENDED_EVENT_ID,
                    OBSERVED_AT.replace(tzinfo=None),
                    PURGE_AFTER,
                )
            ],
            id="naive-observed-at",
        ),
        pytest.param(
            [
                (
                    OVERFLOW_ENDED_EVENT_ID,
                    OBSERVED_AT,
                    PURGE_AFTER + timedelta(microseconds=1),
                )
            ],
            id="inconsistent-purge-after",
        ),
    ),
)
def test_invalid_close_result_rolls_back_and_never_commits(rows: list[object]):
    connection = _FakeConnection(closure_rows=rows)

    with pytest.raises(SecurityAuditOverflowRefused):
        SecurityAuditOverflowRunner(_FakeFactory(connection)).run("host=audit")

    assert connection.rollback_calls == 1
    assert connection.commit_calls == 0
    assert connection.close_calls == 1


@pytest.mark.parametrize(
    ("error", "expected"),
    (
        pytest.param(
            RuntimeError("rollback refusal"),
            SecurityAuditOverflowRefused,
            id="refused",
        ),
        pytest.param(
            psycopg.OperationalError("rollback transport"),
            SecurityAuditOverflowUnavailable,
            id="unavailable",
        ),
    ),
)
def test_no_bucket_rollback_failure_uses_fixed_transport_split(
    error: Exception,
    expected: type[Exception],
):
    connection = _FakeConnection(observation_rows=[], rollback_error=error)

    with pytest.raises(expected):
        SecurityAuditOverflowRunner(_FakeFactory(connection)).run("host=audit")

    assert connection.executed == [(OBSERVE_OVERFLOW_SQL, None)]
    assert connection.rollback_calls == 1
    assert connection.commit_calls == 0
    assert connection.close_calls == 1


def test_precommit_cleanup_failures_do_not_replace_refused_classification():
    connection = _FakeConnection(
        observation_rows=[["malformed"]],
        rollback_error=psycopg.OperationalError("rollback canary"),
        close_error=RuntimeError("close canary"),
    )

    with pytest.raises(SecurityAuditOverflowRefused):
        SecurityAuditOverflowRunner(_FakeFactory(connection)).run("host=audit")

    assert connection.rollback_calls == 1
    assert connection.commit_calls == 0
    assert connection.close_calls == 1


def test_no_bucket_close_failure_cannot_downgrade_known_result():
    connection = _FakeConnection(
        observation_rows=[],
        close_error=RuntimeError("close canary"),
    )

    completed = SecurityAuditOverflowRunner(_FakeFactory(connection)).run(
        "host=audit"
    )

    assert completed == _completed_no_bucket()
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
def test_every_ordinary_commit_exception_is_unknown_without_retry(
    commit_error: Exception,
):
    connection = _FakeConnection(commit_error=commit_error)
    factory = _FakeFactory(connection)

    with pytest.raises(SecurityAuditOverflowOutcomeUnknown):
        SecurityAuditOverflowRunner(factory).run("host=audit")

    assert len(factory.calls) == 1
    assert connection.rollback_calls == 0
    assert connection.commit_calls == 1
    assert connection.close_calls == 1


def test_commit_base_exception_escapes_without_fabricated_terminal_outcome():
    connection = _FakeConnection(commit_error=KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        SecurityAuditOverflowRunner(_FakeFactory(connection)).run("host=audit")

    assert connection.rollback_calls == 0
    assert connection.commit_calls == 1
    assert connection.close_calls == 1


def test_post_commit_close_failure_cannot_downgrade_acknowledgement():
    connection = _FakeConnection(close_error=RuntimeError("close canary"))

    completed = SecurityAuditOverflowRunner(_FakeFactory(connection)).run(
        "host=audit"
    )

    assert completed == _completed_closure()
    assert connection.commit_calls == 1
    assert connection.close_calls == 1


def test_acknowledged_report_has_only_the_fixed_non_count_fields():
    completed = SecurityAuditOverflowRunner(
        _FakeFactory(_FakeConnection())
    ).run("host=audit")

    document = json.loads(completed.report_bytes)

    assert set(document) == {
        "bucketStart",
        "component",
        "observedAt",
        "outcome",
        "overflowEndedEventId",
        "producer",
        "purgeAfter",
        "schema",
    }
    assert "count" not in completed.report_bytes.decode("ascii").lower()


@pytest.mark.parametrize(
    "argv",
    (
        pytest.param(("-h",), id="short-help"),
        pytest.param(("--help",), id="long-help"),
        pytest.param(("--",), id="separator"),
        pytest.param(("value",), id="positional"),
        pytest.param(("--bucket", "2026-08-14T08:00:00Z"), id="bucket"),
        pytest.param(("--producer", "AUTHENTICATION_BOUNDARY_V1"), id="producer"),
        pytest.param(("--limit", "1"), id="limit"),
    ),
)
def test_cli_rejects_every_nonempty_argument_shape_without_running(argv):
    runner = _StubRunner(_completed_closure())

    code, output, error = _run_cli(runner, argv=argv)

    assert code == 2
    assert output.getvalue() == b""
    assert error.getvalue() == (
        b"security-audit overflow closure command is invalid\n"
    )
    assert runner.calls == []


@pytest.mark.parametrize(
    "environ",
    (
        pytest.param({}, id="missing"),
        pytest.param({OVERFLOW_DSN_ENVIRONMENT: "   "}, id="whitespace"),
        pytest.param(
            {OVERFLOW_DSN_ENVIRONMENT: "host='unterminated"},
            id="malformed",
        ),
    ),
)
def test_cli_rejects_invalid_conninfo_without_running(environ):
    runner = _StubRunner(_completed_closure())

    code, output, error = _run_cli(runner, environ=environ)

    assert code == 2
    assert output.getvalue() == b""
    assert error.getvalue() == (
        b"security-audit overflow closure command is invalid\n"
    )
    assert runner.calls == []


@pytest.mark.parametrize(
    ("completed", "expected"),
    (
        pytest.param(
            _completed_closure(),
            EXPECTED_ACKNOWLEDGED_REPORT,
            id="acknowledged",
        ),
        pytest.param(
            _completed_no_bucket(),
            EXPECTED_NO_BUCKET_REPORT,
            id="no-bucket",
        ),
    ),
)
def test_cli_writes_each_exact_success_report_and_flushes(completed, expected):
    runner = _StubRunner(completed)
    output = _RecordingBinaryOutput()

    code, returned_output, error = _run_cli(runner, stdout=output)

    assert code == 0
    assert returned_output is output
    assert bytes(output.value) == expected
    assert output.flush_calls == 1
    assert error.getvalue() == b""
    assert runner.calls == ["host=audit dbname=ofarm_security_audit"]


@pytest.mark.parametrize(
    ("outcome", "exit_code", "line"),
    (
        pytest.param(
            SecurityAuditOverflowRefused("secret"),
            1,
            b"security-audit overflow closure was refused\n",
            id="refused",
        ),
        pytest.param(
            SecurityAuditOverflowUnavailable("secret"),
            3,
            b"security-audit overflow closure is unavailable; "
            b"no commit was sent\n",
            id="unavailable",
        ),
        pytest.param(
            SecurityAuditOverflowOutcomeUnknown("secret"),
            4,
            b"security-audit overflow closure outcome is unknown; "
            b"do not retry automatically\n",
            id="unknown",
        ),
    ),
)
def test_cli_failure_protocol_is_closed_and_secret_free(
    outcome: Exception,
    exit_code: int,
    line: bytes,
):
    runner = _StubRunner(outcome)

    code, output, error = _run_cli(runner)

    assert code == exit_code
    assert output.getvalue() == b""
    assert error.getvalue() == line
    assert b"secret" not in error.getvalue()
    assert len(runner.calls) == 1


def test_real_runner_cli_transport_failure_leaks_no_conninfo_or_exception():
    connection_factory = _FakeFactory(
        error=psycopg.OperationalError("secret-exception-canary")
    )
    runner = SecurityAuditOverflowRunner(connection_factory)
    environ = {
        OVERFLOW_DSN_ENVIRONMENT: (
            "host=secret-host-canary password=secret-password-canary"
        )
    }

    code, output, error = _run_cli(runner, environ=environ)

    assert code == 3
    assert output.getvalue() == b""
    assert error.getvalue() == (
        b"security-audit overflow closure is unavailable; no commit was sent\n"
    )
    assert b"secret" not in error.getvalue()
    assert len(connection_factory.calls) == 1


def test_cli_does_not_invent_state_for_nonconforming_runner_exception():
    runner = _StubRunner(RuntimeError("unexpected secret"))
    output = BytesIO()
    error = BytesIO()

    with pytest.raises(RuntimeError, match="unexpected secret"):
        run_fixed_security_audit_overflow_cli(
            argv=(),
            environ={OVERFLOW_DSN_ENVIRONMENT: "host=audit dbname=audit"},
            stdout=output,
            stderr=error,
            runner=runner,
        )

    assert output.getvalue() == b""
    assert error.getvalue() == b""
    assert len(runner.calls) == 1


@pytest.mark.parametrize(
    ("output", "expected_prefix", "flush_calls"),
    (
        pytest.param(
            _RecordingBinaryOutput(short_write=True),
            EXPECTED_ACKNOWLEDGED_REPORT[:-1],
            0,
            id="short-write",
        ),
        pytest.param(
            _RecordingBinaryOutput(write_error=OSError("write canary")),
            b"",
            0,
            id="write-error",
        ),
        pytest.param(
            _RecordingBinaryOutput(flush_error=OSError("flush canary")),
            EXPECTED_ACKNOWLEDGED_REPORT,
            1,
            id="flush-error",
        ),
    ),
)
def test_cli_reporting_failure_is_exit_five_without_second_database_attempt(
    output: _RecordingBinaryOutput,
    expected_prefix: bytes,
    flush_calls: int,
):
    runner = _StubRunner(_completed_closure())

    code, returned_output, error = _run_cli(runner, stdout=output)

    assert code == 5
    assert returned_output is output
    assert bytes(output.value) == expected_prefix
    assert output.flush_calls == flush_calls
    assert error.getvalue() == (
        b"security-audit overflow closure result reporting failed; "
        b"do not retry automatically\n"
    )
    assert len(runner.calls) == 1


@pytest.mark.parametrize(
    "stderr",
    (
        pytest.param(
            _RecordingBinaryOutput(short_write=True),
            id="short-write",
        ),
        pytest.param(
            _RecordingBinaryOutput(write_error=OSError("write canary")),
            id="write-error",
        ),
        pytest.param(
            _RecordingBinaryOutput(flush_error=OSError("flush canary")),
            id="flush-error",
        ),
    ),
)
def test_diagnostic_delivery_failure_leaves_no_claimed_terminal_protocol(
    stderr: _RecordingBinaryOutput,
):
    runner = _StubRunner(_completed_closure())

    with pytest.raises(OSError):
        _run_cli(runner, argv=("--help",), stderr=stderr)

    assert runner.calls == []


def test_operator_documentation_is_one_shot_and_claim_limited():
    documentation = (PACKAGE_ROOT / "deployment/postgresql/README.md").read_text()

    assert "python -m deployment.postgresql.run_security_audit_overflow" in documentation
    assert "accepts no arguments" in documentation
    assert "ofarm_security_audit_control_login" in documentation
    assert "same idle non-autocommit `READ COMMITTED`" in documentation
    assert "must not retry exit `4`, exit `5`" in documentation
    assert "marked `COUNT_UNKNOWN` before operational closure" in documentation
    assert "does not invoke `mark_overflow_count_unknown`" in documentation
    assert "not a scheduler, drain loop" in documentation


def _clear_live_buckets(state: dict[str, object]) -> None:
    with psycopg.connect(
        str(state["target_admin_dsn"]),
        autocommit=True,
    ) as admin:
        admin.execute(
            "DELETE FROM ofarm_security.operational_security_quota_bucket"
        )


def _current_live_bucket(state: dict[str, object]) -> datetime:
    with psycopg.connect(
        str(state["target_admin_dsn"]),
        autocommit=True,
    ) as admin:
        return admin.execute(
            """
            SELECT pg_catalog.date_bin(
                pg_catalog.make_interval(secs => 60),
                pg_catalog.clock_timestamp(),
                '2000-01-01 00:00:00+00'::pg_catalog.timestamptz
            )
            """
        ).fetchone()[0]


def _insert_live_bucket(
    state: dict[str, object],
    *,
    producer: str,
    component: str,
    bucket_start: datetime,
) -> None:
    with psycopg.connect(
        str(state["target_admin_dsn"]),
        autocommit=True,
    ) as admin:
        admin.execute(
            """
            INSERT INTO ofarm_security.operational_security_quota_bucket (
                producer, component, bucket_start, accepted_event_count,
                overflow_started_at
            ) VALUES (%s, %s, %s, 1024, %s)
            """,
            (
                producer,
                component,
                bucket_start,
                bucket_start + timedelta(seconds=1),
            ),
        )


def _live_overflow_events(
    state: dict[str, object],
    *,
    producer: str,
    component: str,
    bucket_start: datetime,
) -> list[tuple[object, ...]]:
    with psycopg.connect(
        str(state["target_admin_dsn"]),
        autocommit=True,
    ) as admin:
        return admin.execute(
            """
            SELECT event_id, observed_at, purge_after
            FROM ofarm_security.operational_security_event
            WHERE event_kind = 'OVERFLOW_ENDED'
              AND affected_producer = %s
              AND affected_component = %s
              AND interval_start = %s
            ORDER BY observed_at, event_id
            """,
            (producer, component, bucket_start),
        ).fetchall()


def _live_overflow_event_count(state: dict[str, object]) -> int:
    with psycopg.connect(
        str(state["target_admin_dsn"]),
        autocommit=True,
    ) as admin:
        return admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm_security.operational_security_event
            WHERE event_kind = 'OVERFLOW_ENDED'
            """
        ).fetchone()[0]


def _live_bucket_exists(
    state: dict[str, object],
    *,
    producer: str,
    component: str,
    bucket_start: datetime,
) -> bool:
    with psycopg.connect(
        str(state["target_admin_dsn"]),
        autocommit=True,
    ) as admin:
        row = admin.execute(
            """
            SELECT 1
            FROM ofarm_security.operational_security_quota_bucket
            WHERE producer = %s AND component = %s AND bucket_start = %s
            """,
            (producer, component, bucket_start),
        ).fetchone()
    return row == (1,)


class _PausedObservationCursor:
    def __init__(
        self,
        cursor,
        observation_ready: Event,
        closer_committed: Event,
    ) -> None:
        self._cursor = cursor
        self._observation_ready = observation_ready
        self._closer_committed = closer_committed
        self._fetchone_calls = 0

    def fetchone(self) -> object:
        row = self._cursor.fetchone()
        self._fetchone_calls += 1
        if self._fetchone_calls == 2:
            self._observation_ready.set()
            if not self._closer_committed.wait(timeout=10):
                raise TimeoutError("concurrent closer did not commit")
        return row


class _PausedObservationConnection:
    def __init__(
        self,
        connection,
        observation_ready: Event,
        closer_committed: Event,
    ) -> None:
        self._connection = connection
        self._observation_ready = observation_ready
        self._closer_committed = closer_committed

    @property
    def closed(self) -> bool:
        return self._connection.closed

    @property
    def autocommit(self) -> bool:
        return self._connection.autocommit

    @property
    def isolation_level(self) -> IsolationLevel | None:
        return self._connection.isolation_level

    @isolation_level.setter
    def isolation_level(self, value: IsolationLevel | None) -> None:
        self._connection.isolation_level = value

    @property
    def info(self):
        return self._connection.info

    def execute(
        self,
        query: str,
        parameters: tuple[object, ...] | None = None,
    ):
        if parameters is None:
            cursor = self._connection.execute(query)
        else:
            cursor = self._connection.execute(query, parameters)
        if query == OBSERVE_OVERFLOW_SQL:
            return _PausedObservationCursor(
                cursor,
                self._observation_ready,
                self._closer_committed,
            )
        return cursor

    def rollback(self) -> None:
        self._connection.rollback()

    def commit(self) -> None:
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()


class _PausedObservationFactory:
    def __init__(
        self,
        observation_ready: Event,
        closer_committed: Event,
    ) -> None:
        self._observation_ready = observation_ready
        self._closer_committed = closer_committed
        self.calls = 0

    def __call__(
        self,
        conninfo: str,
        *,
        autocommit: bool,
        connect_timeout: int,
        options: str,
    ) -> _PausedObservationConnection:
        self.calls += 1
        connection = psycopg.connect(
            conninfo,
            autocommit=autocommit,
            connect_timeout=connect_timeout,
            options=options,
        )
        return _PausedObservationConnection(
            connection,
            self._observation_ready,
            self._closer_committed,
        )


class _ConcurrentObservationCursor:
    def __init__(self, cursor, barrier: Barrier) -> None:
        self._cursor = cursor
        self._barrier = barrier
        self._fetchone_calls = 0

    def fetchone(self) -> object:
        row = self._cursor.fetchone()
        self._fetchone_calls += 1
        if self._fetchone_calls == 2:
            self._barrier.wait(timeout=10)
        return row


class _ConcurrentObservationConnection:
    def __init__(self, connection, barrier: Barrier) -> None:
        self._connection = connection
        self._barrier = barrier

    @property
    def closed(self) -> bool:
        return self._connection.closed

    @property
    def autocommit(self) -> bool:
        return self._connection.autocommit

    @property
    def isolation_level(self) -> IsolationLevel | None:
        return self._connection.isolation_level

    @isolation_level.setter
    def isolation_level(self, value: IsolationLevel | None) -> None:
        self._connection.isolation_level = value

    @property
    def info(self):
        return self._connection.info

    def execute(
        self,
        query: str,
        parameters: tuple[object, ...] | None = None,
    ):
        if parameters is None:
            cursor = self._connection.execute(query)
        else:
            cursor = self._connection.execute(query, parameters)
        if query == OBSERVE_OVERFLOW_SQL:
            return _ConcurrentObservationCursor(cursor, self._barrier)
        return cursor

    def rollback(self) -> None:
        self._connection.rollback()

    def commit(self) -> None:
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()


class _ImpersonatingConcurrentFactory:
    """Exercise two runner state machines despite the login's limit of one."""

    def __init__(self, admin_dsn: str, barrier: Barrier) -> None:
        self._admin_dsn = admin_dsn
        self._barrier = barrier
        self.calls = 0

    def __call__(
        self,
        conninfo: str,
        *,
        autocommit: bool,
        connect_timeout: int,
        options: str,
    ) -> _ConcurrentObservationConnection:
        parameters = psycopg.conninfo.conninfo_to_dict(conninfo)
        assert parameters["user"] == "ofarm_security_audit_control_login"
        self.calls += 1
        connection = psycopg.connect(
            self._admin_dsn,
            autocommit=True,
            connect_timeout=connect_timeout,
            options=options,
        )
        connection.execute(
            "SET SESSION AUTHORIZATION ofarm_security_audit_control_login"
        )
        connection.autocommit = autocommit
        return _ConcurrentObservationConnection(connection, self._barrier)


def test_live_no_bucket_is_a_rolled_back_success_without_event(
    migrated_audit_service,
):
    state = migrated_audit_service
    _clear_live_buckets(state)
    before = _live_overflow_event_count(state)

    completed = SecurityAuditOverflowRunner().run(
        role_dsn(state, "ofarm_security_audit_control_login")
    )

    assert completed == _completed_no_bucket()
    assert _live_overflow_event_count(state) == before


def test_live_wrong_role_refuses_without_closing_a_bucket(
    migrated_audit_service,
):
    state = migrated_audit_service
    _clear_live_buckets(state)
    current_bucket = _current_live_bucket(state)
    bucket_start = current_bucket - timedelta(minutes=10)
    _insert_live_bucket(
        state,
        producer="AUTHENTICATION_BOUNDARY_V1",
        component="AUTHENTICATION",
        bucket_start=bucket_start,
    )
    try:
        with pytest.raises(SecurityAuditOverflowRefused):
            SecurityAuditOverflowRunner().run(
                role_dsn(state, "ofarm_security_audit_reader_login")
            )

        assert _live_bucket_exists(
            state,
            producer="AUTHENTICATION_BOUNDARY_V1",
            component="AUTHENTICATION",
            bucket_start=bucket_start,
        )
        assert _live_overflow_events(
            state,
            producer="AUTHENTICATION_BOUNDARY_V1",
            component="AUTHENTICATION",
            bucket_start=bucket_start,
        ) == []
    finally:
        _clear_live_buckets(state)


def test_live_runner_closes_only_the_database_selected_oldest_bucket(
    migrated_audit_service,
):
    state = migrated_audit_service
    _clear_live_buckets(state)
    current_bucket = _current_live_bucket(state)
    oldest = current_bucket - timedelta(minutes=30)
    newer = current_bucket - timedelta(minutes=20)
    _insert_live_bucket(
        state,
        producer="AUTHENTICATION_BOUNDARY_V1",
        component="AUTHENTICATION",
        bucket_start=oldest,
    )
    _insert_live_bucket(
        state,
        producer="REQUEST_ROUTER_BOUNDARY_V1",
        component="REQUEST_ROUTER",
        bucket_start=newer,
    )
    try:
        completed = SecurityAuditOverflowRunner().run(
            role_dsn(state, "ofarm_security_audit_control_login")
        )

        assert completed.result is not None
        assert completed.result.bucket == SecurityAuditOverflowBucket(
            producer="AUTHENTICATION_BOUNDARY_V1",
            component="AUTHENTICATION",
            bucket_start=oldest,
        )
        events = _live_overflow_events(
            state,
            producer="AUTHENTICATION_BOUNDARY_V1",
            component="AUTHENTICATION",
            bucket_start=oldest,
        )
        assert events == [
            (
                completed.result.overflow_ended_event_id,
                completed.result.observed_at,
                completed.result.purge_after,
            )
        ]
        assert not _live_bucket_exists(
            state,
            producer="AUTHENTICATION_BOUNDARY_V1",
            component="AUTHENTICATION",
            bucket_start=oldest,
        )
        assert _live_bucket_exists(
            state,
            producer="REQUEST_ROUTER_BOUNDARY_V1",
            component="REQUEST_ROUTER",
            bucket_start=newer,
        )
    finally:
        _clear_live_buckets(state)


def test_live_runner_acknowledges_concurrent_idempotent_closure_identity(
    migrated_audit_service,
):
    state = migrated_audit_service
    _clear_live_buckets(state)
    bucket_start = _current_live_bucket(state) - timedelta(minutes=40)
    _insert_live_bucket(
        state,
        producer="AUTHENTICATION_BOUNDARY_V1",
        component="AUTHENTICATION",
        bucket_start=bucket_start,
    )
    observation_ready = Event()
    closer_committed = Event()
    factory = _PausedObservationFactory(
        observation_ready,
        closer_committed,
    )
    runner = SecurityAuditOverflowRunner(factory)
    conninfo = role_dsn(state, "ofarm_security_audit_control_login")
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(runner.run, conninfo)
            assert observation_ready.wait(timeout=10)
            try:
                with psycopg.connect(
                    str(state["target_admin_dsn"]),
                    autocommit=True,
                ) as concurrent_closer:
                    concurrent_closer.execute(
                        "SET SESSION AUTHORIZATION "
                        "ofarm_security_audit_control_login"
                    )
                    concurrent_closer.autocommit = False
                    closure_row = concurrent_closer.execute(
                        CLOSE_OVERFLOW_SQL,
                        (
                            "AUTHENTICATION_BOUNDARY_V1",
                            "AUTHENTICATION",
                            bucket_start,
                        ),
                    ).fetchone()
                    concurrent_closer.commit()
            finally:
                closer_committed.set()
            completed = future.result(timeout=15)

        assert factory.calls == 1
        assert completed.result is not None
        assert closure_row is not None
        assert completed.result.overflow_ended_event_id == closure_row[0]
        events = _live_overflow_events(
            state,
            producer="AUTHENTICATION_BOUNDARY_V1",
            component="AUTHENTICATION",
            bucket_start=bucket_start,
        )
        assert len(events) == 1
        assert events[0][0] == completed.result.overflow_ended_event_id
    finally:
        _clear_live_buckets(state)


def test_live_two_runner_state_machines_report_one_closure_identity(
    migrated_audit_service,
):
    state = migrated_audit_service
    _clear_live_buckets(state)
    bucket_start = _current_live_bucket(state) - timedelta(minutes=45)
    _insert_live_bucket(
        state,
        producer="AUTHENTICATION_BOUNDARY_V1",
        component="AUTHENTICATION",
        bucket_start=bucket_start,
    )
    barrier = Barrier(2)
    factory = _ImpersonatingConcurrentFactory(
        str(state["target_admin_dsn"]),
        barrier,
    )
    runner = SecurityAuditOverflowRunner(factory)
    conninfo = role_dsn(state, "ofarm_security_audit_control_login")
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(runner.run, conninfo) for _ in range(2)]
            completed = [future.result(timeout=15) for future in futures]

        assert factory.calls == 2
        assert all(result.result is not None for result in completed)
        event_ids = {
            result.result.overflow_ended_event_id
            for result in completed
            if result.result is not None
        }
        assert len(event_ids) == 1
        assert completed[0].report_bytes == completed[1].report_bytes
        events = _live_overflow_events(
            state,
            producer="AUTHENTICATION_BOUNDARY_V1",
            component="AUTHENTICATION",
            bucket_start=bucket_start,
        )
        assert len(events) == 1
        assert events[0][0] == event_ids.pop()
    finally:
        _clear_live_buckets(state)


def test_live_conflicting_lock_refuses_with_fixed_timeout_and_no_commit(
    migrated_audit_service,
):
    state = migrated_audit_service
    _clear_live_buckets(state)
    bucket_start = _current_live_bucket(state) - timedelta(minutes=50)
    _insert_live_bucket(
        state,
        producer="AUTHENTICATION_BOUNDARY_V1",
        component="AUTHENTICATION",
        bucket_start=bucket_start,
    )
    try:
        with psycopg.connect(str(state["target_admin_dsn"])) as locker:
            locker.execute(
                "LOCK TABLE ofarm_security.operational_security_event "
                "IN ACCESS EXCLUSIVE MODE"
            )
            started_at = monotonic()
            with pytest.raises(SecurityAuditOverflowRefused):
                SecurityAuditOverflowRunner().run(
                    role_dsn(state, "ofarm_security_audit_control_login")
                )
            elapsed = monotonic() - started_at

        assert elapsed < 5
        assert _live_bucket_exists(
            state,
            producer="AUTHENTICATION_BOUNDARY_V1",
            component="AUTHENTICATION",
            bucket_start=bucket_start,
        )
        assert _live_overflow_events(
            state,
            producer="AUTHENTICATION_BOUNDARY_V1",
            component="AUTHENTICATION",
            bucket_start=bucket_start,
        ) == []
    finally:
        _clear_live_buckets(state)
