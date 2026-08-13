"""Focused tests for one-shot bounded security-audit reader execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO, StringIO
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import IsolationLevel
from psycopg.pq import TransactionStatus

from deployment.postgresql.audit_contract import (
    ACCESS_INTENT_EXPIRY_SECONDS,
    CORRELATION_HMAC_DOMAIN,
    EVENT_FORMAT_IDENTITY,
    QUERY_ACCESS_PURPOSE_IDENTITY,
    QUERY_FUNCTION_IDENTITY,
    QUERY_MAX_BYTES,
    QUERY_MAX_ROWS,
    REDACTION_POLICY_IDENTITY,
    RETENTION_POLICY_IDENTITY,
    RETENTION_SECONDS,
)
from deployment.postgresql.run_security_audit_query import (
    CONTROL_DSN_ENVIRONMENT,
    READER_DSN_ENVIRONMENT,
    run_fixed_security_audit_query_cli,
)
from deployment.postgresql.security_audit_query import (
    ACCESS_INTENT_SQL,
    AcknowledgedSecurityAuditQuery,
    BOUNDED_QUERY_SQL,
    QUERY_CONNECT_TIMEOUT_SECONDS,
    QUERY_CONTROL_CONNECTION_OPTIONS,
    QUERY_READER_CONNECTION_OPTIONS,
    QUERY_REPORT_SCHEMA,
    SecurityAuditAccessIntent,
    SecurityAuditQueryControlUnavailable,
    SecurityAuditQueryCursor,
    SecurityAuditQueryFailed,
    SecurityAuditQueryOutcomeUnknown,
    SecurityAuditQueryRefused,
    SecurityAuditQueryRunner,
)
from kernel.tests.postgresql_audit_support import (
    audit_service_fixture,  # noqa: F401
    role_dsn,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
ACCESS_EVENT_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
DATA_CUT = datetime(2026, 8, 13, 10, 20, 30, 123456, tzinfo=timezone.utc)
EXPIRES_AT = DATA_CUT + timedelta(seconds=ACCESS_INTENT_EXPIRY_SECONDS)
EVENT_ID = UUID("11111111-1111-4111-8111-111111111111")
EVENT_AT = DATA_CUT - timedelta(seconds=10)
PURGE_AFTER = EVENT_AT + timedelta(seconds=RETENTION_SECONDS)
REPORT_BYTES = b'{"acknowledged":true}\n'


def _intent_row() -> tuple[object, ...]:
    return ACCESS_EVENT_ID, DATA_CUT, EXPIRES_AT


def _pretenant_row(
    *,
    event_id: UUID = EVENT_ID,
    observed_at: datetime = EVENT_AT,
    producer: str = "AUTHENTICATION_BOUNDARY_V1",
    component: str = "AUTHENTICATION",
    reason: str = "TENANT_PARTY_PIN_REFUSED",
) -> tuple[object, ...]:
    return (
        event_id,
        observed_at,
        observed_at + timedelta(seconds=RETENTION_SECONDS),
        "PRE_TENANT_FAILURE",
        producer,
        component,
        reason,
        CORRELATION_HMAC_DOMAIN,
        1,
        bytes(range(32)),
        EVENT_FORMAT_IDENTITY,
        REDACTION_POLICY_IDENTITY,
        RETENTION_POLICY_IDENTITY,
        bytes(reversed(range(32))),
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )


def _maintenance_row(event_kind: str) -> tuple[object, ...]:
    values = list(_pretenant_row(reason="CREDENTIAL_MISSING"))
    values[3] = event_kind
    values[4] = "SECURITY_OPERATIONS_V1"
    values[5] = (
        "AUDIT_RETENTION" if event_kind == "AUDIT_RETENTION" else "AUDIT_CONTROL"
    )
    values[6:10] = [None, None, None, None]
    if event_kind == "AUDIT_ACCESS":
        values[14:22] = [
            QUERY_ACCESS_PURPOSE_IDENTITY,
            QUERY_FUNCTION_IDENTITY,
            EVENT_AT,
            None,
            None,
            QUERY_MAX_ROWS,
            QUERY_MAX_BYTES,
            EVENT_AT + timedelta(seconds=ACCESS_INTENT_EXPIRY_SECONDS),
        ]
    elif event_kind == "AUDIT_RETENTION":
        values[22:24] = [EVENT_AT - timedelta(days=30), 17]
    elif event_kind == "AUDIT_GAP":
        values[24:30] = [
            EVENT_AT - timedelta(minutes=2),
            EVENT_AT - timedelta(minutes=1),
            9,
            False,
            None,
            None,
        ]
    elif event_kind == "OVERFLOW_STARTED":
        values[24:30] = [
            EVENT_AT - timedelta(minutes=2),
            EVENT_AT - timedelta(minutes=1),
            None,
            False,
            "AUTHENTICATION_BOUNDARY_V1",
            "AUTHENTICATION",
        ]
    elif event_kind == "OVERFLOW_ENDED":
        values[24:30] = [
            EVENT_AT - timedelta(minutes=2),
            EVENT_AT - timedelta(minutes=1),
            None,
            True,
            "REQUEST_ROUTER_BOUNDARY_V1",
            "REQUEST_ROUTER",
        ]
    else:
        raise AssertionError(f"unsupported fixture event kind: {event_kind}")
    return tuple(values)


def _replace(row: tuple[object, ...], index: int, value: object) -> tuple[object, ...]:
    changed = list(row)
    changed[index] = value
    return tuple(changed)


@dataclass
class _FakeInfo:
    transaction_status: TransactionStatus = TransactionStatus.IDLE


class _FakeCursor:
    def __init__(
        self,
        rows: list[object],
        *,
        fetchmany_error: BaseException | None = None,
    ) -> None:
        self.rows = list(rows)
        self.fetchmany_sizes: list[int] = []
        self._fetchmany_error = fetchmany_error

    def fetchone(self) -> object:
        if not self.rows:
            return None
        return self.rows.pop(0)

    def fetchmany(self, size: int) -> list[object]:
        self.fetchmany_sizes.append(size)
        if self._fetchmany_error is not None:
            raise self._fetchmany_error
        selected = self.rows[:size]
        del self.rows[:size]
        return selected


class _FakeConnection:
    def __init__(
        self,
        rows: list[object],
        *,
        autocommit: bool,
        closed: bool = False,
        transaction_status: TransactionStatus = TransactionStatus.IDLE,
        execute_error: BaseException | None = None,
        fetchmany_error: BaseException | None = None,
        commit_error: BaseException | None = None,
        isolation_error: BaseException | None = None,
        close_error: Exception | None = None,
    ) -> None:
        self.closed = closed
        self.autocommit = autocommit
        self.info = _FakeInfo(transaction_status)
        self.cursor = _FakeCursor(rows, fetchmany_error=fetchmany_error)
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self._isolation_level: IsolationLevel | None = None
        self._execute_error = execute_error
        self._commit_error = commit_error
        self._isolation_error = isolation_error
        self._close_error = close_error
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
        params: tuple[object, ...],
    ) -> _FakeCursor:
        self.executed.append((query, params))
        if self._execute_error is not None:
            raise self._execute_error
        return self.cursor

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
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
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
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        assert isinstance(outcome, _FakeConnection)
        return outcome


class _StubRunner:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.calls: list[
            tuple[str, str, SecurityAuditQueryCursor | None]
        ] = []

    def run(
        self,
        control_conninfo: str,
        reader_conninfo: str,
        cursor: SecurityAuditQueryCursor | None,
    ) -> AcknowledgedSecurityAuditQuery:
        self.calls.append((control_conninfo, reader_conninfo, cursor))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        assert isinstance(self.outcome, AcknowledgedSecurityAuditQuery)
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


def _acknowledged(report: bytes = REPORT_BYTES) -> AcknowledgedSecurityAuditQuery:
    return AcknowledgedSecurityAuditQuery(
        intent=SecurityAuditAccessIntent(
            access_event_id=ACCESS_EVENT_ID,
            data_cut=DATA_CUT,
            expires_at=EXPIRES_AT,
        ),
        input_cursor=None,
        events=(),
        next_cursor=None,
        report_bytes=report,
    )


def _factory_for_rows(
    rows: list[object],
    *,
    control_kwargs: dict[str, object] | None = None,
    reader_kwargs: dict[str, object] | None = None,
) -> tuple[_FakeFactory, _FakeConnection, _FakeConnection]:
    control = _FakeConnection(
        [_intent_row()],
        autocommit=False,
        **(control_kwargs or {}),
    )
    reader = _FakeConnection(
        rows,
        autocommit=True,
        **(reader_kwargs or {}),
    )
    return _FakeFactory([control, reader]), control, reader


def _run_cli(
    runner: _StubRunner | SecurityAuditQueryRunner,
    *,
    argv: tuple[str, ...] = (),
    environ: dict[str, str] | None = None,
    stdout: _RecordingOutput | BytesIO | None = None,
) -> tuple[int, _RecordingOutput | BytesIO, StringIO]:
    output = stdout or BytesIO()
    error = StringIO()
    code = run_fixed_security_audit_query_cli(
        argv=argv,
        environ=(
            {
                CONTROL_DSN_ENVIRONMENT: "host=control dbname=audit",
                READER_DSN_ENVIRONMENT: "host=reader dbname=audit",
            }
            if environ is None
            else environ
        ),
        stdout=output,
        stderr=error,
        runner=runner,
    )
    return code, output, error


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        pytest.param(
            "2026-08-13T10:20:30.123456Z/11111111-1111-4111-8111-111111111111",
            SecurityAuditQueryCursor(EVENT_AT + timedelta(seconds=10), EVENT_ID),
            id="canonical",
        ),
    ),
)
def test_cursor_parser_accepts_only_the_canonical_pair(value, expected):
    parsed = SecurityAuditQueryCursor.parse(value)

    assert parsed == expected
    assert parsed.render() == value


@pytest.mark.parametrize(
    "value",
    (
        pytest.param("", id="empty"),
        pytest.param("2026-08-13T10:20:30Z/" + str(EVENT_ID), id="no-fraction"),
        pytest.param(
            "2026-08-13T12:20:30.123456+02:00/" + str(EVENT_ID),
            id="offset",
        ),
        pytest.param(
            "2026-08-13T10:20:30.123456Z/"
            "11111111-1111-4111-8111-11111111111A",
            id="uppercase-uuid",
        ),
        pytest.param(
            "2026-08-13T10:20:30.123456Z/"
            "00000000-0000-0000-0000-000000000000",
            id="nil-uuid",
        ),
        pytest.param(
            " 2026-08-13T10:20:30.123456Z/" + str(EVENT_ID),
            id="whitespace",
        ),
        pytest.param(None, id="non-string"),
    ),
)
def test_cursor_parser_rejects_noncanonical_or_incomplete_values(value):
    with pytest.raises(ValueError):
        SecurityAuditQueryCursor.parse(value)


def test_runner_submits_one_fixed_intent_then_one_equal_query():
    factory, control, reader = _factory_for_rows([_pretenant_row()])
    acknowledged = SecurityAuditQueryRunner(factory).run(
        "host=control options='-c statement_timeout=0'",
        "host=reader options='-c work_mem=64MB'",
        None,
    )

    assert factory.calls == [
        (
            "host=control options='-c statement_timeout=0'",
            False,
            QUERY_CONNECT_TIMEOUT_SECONDS,
            QUERY_CONTROL_CONNECTION_OPTIONS,
        ),
        (
            "host=reader options='-c work_mem=64MB'",
            True,
            QUERY_CONNECT_TIMEOUT_SECONDS,
            QUERY_READER_CONNECTION_OPTIONS,
        ),
    ]
    assert control.executed == [
        (
            ACCESS_INTENT_SQL,
            (
                QUERY_ACCESS_PURPOSE_IDENTITY,
                QUERY_FUNCTION_IDENTITY,
                None,
                None,
                QUERY_MAX_ROWS,
                QUERY_MAX_BYTES,
            ),
        )
    ]
    assert reader.executed == [
        (
            BOUNDED_QUERY_SQL,
            (ACCESS_EVENT_ID, None, None, QUERY_MAX_ROWS, QUERY_MAX_BYTES),
        )
    ]
    assert control.isolation_level == IsolationLevel.READ_COMMITTED
    assert control.rollback_calls == 0
    assert control.commit_calls == 1
    assert control.close_calls == 1
    assert reader.cursor.fetchmany_sizes == [QUERY_MAX_ROWS + 1]
    assert reader.close_calls == 1
    assert acknowledged.next_cursor == SecurityAuditQueryCursor(EVENT_AT, EVENT_ID)

    document = json.loads(acknowledged.report_bytes)
    assert acknowledged.report_bytes == (
        json.dumps(
            document,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        + b"\n"
    )
    assert list(document) == sorted(document)
    assert document == {
        "accessEventId": str(ACCESS_EVENT_ID),
        "dataCut": "2026-08-13T10:20:30.123456Z",
        "events": [
            {
                "accessCursorEventId": None,
                "accessCursorObservedAt": None,
                "accessDataCut": None,
                "accessExpiresAt": None,
                "accessFunctionIdentity": None,
                "accessMaxBytes": None,
                "accessMaxRows": None,
                "accessPurpose": None,
                "affectedComponent": None,
                "affectedProducer": None,
                "appendInputFingerprint": bytes(reversed(range(32))).hex(),
                "component": "AUTHENTICATION",
                "correlationHmacDomain": CORRELATION_HMAC_DOMAIN,
                "correlationHmacKeyVersion": 1,
                "correlationHmacValue": bytes(range(32)).hex(),
                "eventFormatIdentity": EVENT_FORMAT_IDENTITY,
                "eventId": str(EVENT_ID),
                "eventKind": "PRE_TENANT_FAILURE",
                "intervalCountUnknown": None,
                "intervalEnd": None,
                "intervalEventCount": None,
                "intervalStart": None,
                "observedAt": "2026-08-13T10:20:20.123456Z",
                "producer": "AUTHENTICATION_BOUNDARY_V1",
                "purgeAfter": "2026-09-12T10:20:20.123456Z",
                "reason": "TENANT_PARTY_PIN_REFUSED",
                "redactionPolicyIdentity": REDACTION_POLICY_IDENTITY,
                "retentionCutoff": None,
                "retentionDeletedCount": None,
                "retentionPolicyIdentity": RETENTION_POLICY_IDENTITY,
            }
        ],
        "expiresAt": "2026-08-13T10:25:30.123456Z",
        "functionIdentity": QUERY_FUNCTION_IDENTITY,
        "inputCursor": None,
        "maxBytes": QUERY_MAX_BYTES,
        "maxRows": QUERY_MAX_ROWS,
        "nextCursor": (
            "2026-08-13T10:20:20.123456Z/"
            "11111111-1111-4111-8111-111111111111"
        ),
        "outcome": "ACKNOWLEDGED",
        "purpose": QUERY_ACCESS_PURPOSE_IDENTITY,
        "returnedRowCount": 1,
        "schemaVersion": QUERY_REPORT_SCHEMA,
    }


def test_runner_binds_one_immutable_cursor_to_both_database_calls():
    cursor = SecurityAuditQueryCursor(
        EVENT_AT + timedelta(seconds=1),
        UUID("ffffffff-ffff-4fff-8fff-ffffffffffff"),
    )
    factory, control, reader = _factory_for_rows([_pretenant_row()])

    acknowledged = SecurityAuditQueryRunner(factory).run(
        "host=control", "host=reader", cursor
    )

    expected_cursor_values = (cursor.observed_at, cursor.event_id)
    assert control.executed[0][1][2:4] == expected_cursor_values
    assert reader.executed[0][1][1:3] == expected_cursor_values
    assert acknowledged.input_cursor is cursor
    assert json.loads(acknowledged.report_bytes)["inputCursor"] == cursor.render()


@pytest.mark.parametrize(
    "event_kind",
    (
        "AUDIT_ACCESS",
        "AUDIT_RETENTION",
        "AUDIT_GAP",
        "OVERFLOW_STARTED",
        "OVERFLOW_ENDED",
    ),
)
def test_runner_accepts_every_valid_maintenance_event_shape(event_kind):
    factory, _, _ = _factory_for_rows([_maintenance_row(event_kind)])

    acknowledged = SecurityAuditQueryRunner(factory).run(
        "host=control", "host=reader", None
    )

    event = acknowledged.events[0]
    document = json.loads(acknowledged.report_bytes)["events"][0]
    assert event.event_kind == event_kind
    assert document["eventKind"] == event_kind
    if event.access_max_bytes is not None:
        assert document["accessMaxBytes"] == str(event.access_max_bytes)
    if event.retention_deleted_count is not None:
        assert document["retentionDeletedCount"] == str(
            event.retention_deleted_count
        )
    if event.interval_event_count is not None:
        assert document["intervalEventCount"] == str(event.interval_event_count)


def test_retired_authentication_and_router_reasons_remain_readable_unchanged():
    router_id = UUID("22222222-2222-4222-8222-222222222222")
    rows = [
        _pretenant_row(reason="TENANT_PARTY_PIN_REFUSED"),
        _pretenant_row(
            event_id=router_id,
            observed_at=EVENT_AT - timedelta(microseconds=1),
            producer="REQUEST_ROUTER_BOUNDARY_V1",
            component="REQUEST_ROUTER",
            reason="SECURITY_ROUTE_REFUSED",
        ),
    ]
    factory, _, _ = _factory_for_rows(rows)

    acknowledged = SecurityAuditQueryRunner(factory).run(
        "host=control", "host=reader", None
    )

    assert [event.reason for event in acknowledged.events] == [
        "TENANT_PARTY_PIN_REFUSED",
        "SECURITY_ROUTE_REFUSED",
    ]
    assert [
        event["reason"] for event in json.loads(acknowledged.report_bytes)["events"]
    ] == ["TENANT_PARTY_PIN_REFUSED", "SECURITY_ROUTE_REFUSED"]


def test_control_connection_factory_failure_is_unavailable_without_retry():
    factory = _FakeFactory([psycopg.OperationalError("secret control route")])

    with pytest.raises(SecurityAuditQueryControlUnavailable):
        SecurityAuditQueryRunner(factory).run("host=control", "host=reader", None)

    assert len(factory.calls) == 1


@pytest.mark.parametrize(
    ("closed", "autocommit", "status"),
    (
        pytest.param(True, False, TransactionStatus.IDLE, id="closed"),
        pytest.param(False, True, TransactionStatus.IDLE, id="autocommit"),
        pytest.param(False, False, TransactionStatus.INTRANS, id="in-transaction"),
    ),
)
def test_invalid_control_state_refuses_before_intent_or_reader(
    closed,
    autocommit,
    status,
):
    control = _FakeConnection(
        [_intent_row()],
        autocommit=autocommit,
        closed=closed,
        transaction_status=status,
    )
    factory = _FakeFactory([control])

    with pytest.raises(SecurityAuditQueryRefused):
        SecurityAuditQueryRunner(factory).run("host=control", "host=reader", None)

    assert len(factory.calls) == 1
    assert control.executed == []
    assert control.commit_calls == 0
    assert control.close_calls == 1


def test_isolation_selection_failure_refuses_before_intent_or_reader():
    control = _FakeConnection(
        [_intent_row()],
        autocommit=False,
        isolation_error=RuntimeError("secret isolation failure"),
    )
    factory = _FakeFactory([control])

    with pytest.raises(SecurityAuditQueryRefused):
        SecurityAuditQueryRunner(factory).run("host=control", "host=reader", None)

    assert len(factory.calls) == 1
    assert control.executed == []
    assert control.commit_calls == 0


@pytest.mark.parametrize(
    "rows",
    (
        pytest.param([], id="missing"),
        pytest.param([list(_intent_row())], id="non-tuple"),
        pytest.param([_intent_row()[:-1]], id="short"),
        pytest.param([_intent_row(), _intent_row()], id="duplicate"),
        pytest.param(
            [(UUID(int=0), DATA_CUT, EXPIRES_AT)],
            id="nil-id",
        ),
        pytest.param(
            [(ACCESS_EVENT_ID, DATA_CUT.replace(tzinfo=None), EXPIRES_AT)],
            id="naive-cut",
        ),
        pytest.param(
            [
                (
                    ACCESS_EVENT_ID,
                    DATA_CUT,
                    EXPIRES_AT + timedelta(microseconds=1),
                )
            ],
            id="wrong-expiry",
        ),
    ),
)
def test_invalid_intent_result_rolls_back_and_never_opens_reader(rows):
    control = _FakeConnection(list(rows), autocommit=False)
    factory = _FakeFactory([control])

    with pytest.raises(SecurityAuditQueryRefused):
        SecurityAuditQueryRunner(factory).run("host=control", "host=reader", None)

    assert len(factory.calls) == 1
    assert control.rollback_calls == 1
    assert control.commit_calls == 0
    assert control.close_calls == 1


def test_control_execute_failure_rolls_back_without_reader_or_retry():
    control = _FakeConnection(
        [_intent_row()],
        autocommit=False,
        execute_error=psycopg.errors.LockNotAvailable("secret database refusal"),
    )
    factory = _FakeFactory([control])

    with pytest.raises(SecurityAuditQueryRefused):
        SecurityAuditQueryRunner(factory).run("host=control", "host=reader", None)

    assert len(factory.calls) == 1
    assert control.rollback_calls == 1
    assert control.commit_calls == 0


@pytest.mark.parametrize(
    "commit_error",
    (
        pytest.param(psycopg.OperationalError("secret transport"), id="transport"),
        pytest.param(psycopg.DatabaseError("secret database"), id="database"),
    ),
)
def test_every_commit_exception_is_unknown_and_never_opens_reader(commit_error):
    control = _FakeConnection(
        [_intent_row()],
        autocommit=False,
        commit_error=commit_error,
    )
    factory = _FakeFactory([control])

    with pytest.raises(SecurityAuditQueryOutcomeUnknown):
        SecurityAuditQueryRunner(factory).run("host=control", "host=reader", None)

    assert len(factory.calls) == 1
    assert control.rollback_calls == 0
    assert control.commit_calls == 1
    assert control.close_calls == 1


def test_reader_factory_failure_occurs_only_after_acknowledged_intent():
    control = _FakeConnection([_intent_row()], autocommit=False)
    factory = _FakeFactory(
        [control, psycopg.OperationalError("secret reader route")]
    )

    with pytest.raises(SecurityAuditQueryFailed):
        SecurityAuditQueryRunner(factory).run("host=control", "host=reader", None)

    assert len(factory.calls) == 2
    assert control.commit_calls == 1
    assert control.close_calls == 1


@pytest.mark.parametrize(
    ("closed", "autocommit", "status"),
    (
        pytest.param(True, True, TransactionStatus.IDLE, id="closed"),
        pytest.param(False, False, TransactionStatus.IDLE, id="not-autocommit"),
        pytest.param(False, True, TransactionStatus.INTRANS, id="in-transaction"),
    ),
)
def test_invalid_reader_state_is_post_intent_failure_without_query(
    closed,
    autocommit,
    status,
):
    reader = _FakeConnection(
        [_pretenant_row()],
        autocommit=autocommit,
        closed=closed,
        transaction_status=status,
    )
    control = _FakeConnection([_intent_row()], autocommit=False)
    factory = _FakeFactory([control, reader])

    with pytest.raises(SecurityAuditQueryFailed):
        SecurityAuditQueryRunner(factory).run("host=control", "host=reader", None)

    assert control.commit_calls == 1
    assert reader.executed == []
    assert reader.close_calls == 1


def test_reader_execute_failure_is_post_intent_failure_without_retry():
    factory, control, reader = _factory_for_rows(
        [_pretenant_row()],
        reader_kwargs={
            "execute_error": psycopg.OperationalError("secret query failure")
        },
    )

    with pytest.raises(SecurityAuditQueryFailed):
        SecurityAuditQueryRunner(factory).run("host=control", "host=reader", None)

    assert control.commit_calls == 1
    assert len(reader.executed) == 1
    assert len(factory.calls) == 2
    assert reader.close_calls == 1


def test_row_fetch_failure_is_exit_five_without_retry_or_output():
    factory, control, reader = _factory_for_rows(
        [_pretenant_row()],
        reader_kwargs={
            "fetchmany_error": psycopg.OperationalError(
                "secret row fetch failure"
            )
        },
    )

    code, output, error = _run_cli(SecurityAuditQueryRunner(factory))

    assert code == 5
    assert output.getvalue() == b""
    assert error.getvalue() == (
        "security-audit query intent committed but no complete report is "
        "available; do not retry automatically\n"
    )
    assert control.commit_calls == 1
    assert len(factory.calls) == 2
    assert len(reader.executed) == 1
    assert reader.cursor.fetchmany_sizes == [QUERY_MAX_ROWS + 1]
    assert reader.close_calls == 1


@pytest.mark.parametrize(
    ("row", "identifier"),
    (
        pytest.param(list(_pretenant_row()), "non-tuple", id="non-tuple"),
        pytest.param(_pretenant_row()[:-1], "short", id="short"),
        pytest.param(_replace(_pretenant_row(), 0, UUID(int=0)), "uuid", id="nil-id"),
        pytest.param(
            _replace(_pretenant_row(), 1, EVENT_AT.replace(tzinfo=None)),
            "time",
            id="naive-time",
        ),
        pytest.param(
            _replace(_pretenant_row(), 2, PURGE_AFTER + timedelta(microseconds=1)),
            "retention",
            id="wrong-retention",
        ),
        pytest.param(
            _replace(_pretenant_row(), 3, "UNKNOWN"),
            "kind",
            id="unknown-kind",
        ),
        pytest.param(
            _replace(_pretenant_row(), 4, "UNKNOWN_PRODUCER"),
            "producer",
            id="wrong-producer",
        ),
        pytest.param(_replace(_pretenant_row(), 6, ""), "reason", id="empty-reason"),
        pytest.param(
            _replace(_pretenant_row(), 8, True),
            "hmac-version",
            id="boolean-hmac-version",
        ),
        pytest.param(
            _replace(_pretenant_row(), 8, 99),
            "hmac-version",
            id="unknown-hmac-version",
        ),
        pytest.param(
            _replace(_pretenant_row(), 9, bytes(31)),
            "hmac",
            id="short-hmac",
        ),
        pytest.param(
            _replace(_pretenant_row(), 10, "WRONG_FORMAT"),
            "policy",
            id="wrong-format",
        ),
        pytest.param(
            _replace(_pretenant_row(), 13, bytes(31)),
            "fingerprint",
            id="short-fingerprint",
        ),
        pytest.param(
            _replace(_pretenant_row(), 14, QUERY_ACCESS_PURPOSE_IDENTITY),
            "extension",
            id="unexpected-access-field",
        ),
        pytest.param(
            _replace(_pretenant_row(), 22, EVENT_AT),
            "extension",
            id="unexpected-retention-field",
        ),
        pytest.param(
            _replace(_pretenant_row(), 24, EVENT_AT),
            "extension",
            id="unexpected-interval-field",
        ),
    ),
)
def test_malformed_carrier_is_refused_before_any_report(row, identifier):
    factory, control, reader = _factory_for_rows([row])

    with pytest.raises(SecurityAuditQueryFailed):
        SecurityAuditQueryRunner(factory).run("host=control", "host=reader", None)

    assert identifier
    assert control.commit_calls == 1
    assert reader.close_calls == 1


def test_result_refuses_257th_row_without_a_second_query_or_fetch():
    rows = [
        _pretenant_row(
            event_id=UUID(int=index + 1),
            observed_at=EVENT_AT - timedelta(microseconds=index),
            reason="CREDENTIAL_MISSING",
        )
        for index in range(QUERY_MAX_ROWS + 1)
    ]
    factory, control, reader = _factory_for_rows(rows)

    with pytest.raises(SecurityAuditQueryFailed):
        SecurityAuditQueryRunner(factory).run("host=control", "host=reader", None)

    assert control.commit_calls == 1
    assert len(reader.executed) == 1
    assert reader.cursor.fetchmany_sizes == [QUERY_MAX_ROWS + 1]
    assert len(factory.calls) == 2


def test_result_refuses_duplicate_or_ascending_order():
    rows = [
        _pretenant_row(),
        _pretenant_row(
            event_id=UUID("ffffffff-ffff-4fff-8fff-ffffffffffff"),
            observed_at=EVENT_AT + timedelta(microseconds=1),
        ),
    ]
    factory, _, _ = _factory_for_rows(rows)

    with pytest.raises(SecurityAuditQueryFailed):
        SecurityAuditQueryRunner(factory).run("host=control", "host=reader", None)


def test_result_refuses_row_at_or_above_input_cursor():
    cursor = SecurityAuditQueryCursor(EVENT_AT, EVENT_ID)
    factory, _, _ = _factory_for_rows([_pretenant_row()])

    with pytest.raises(SecurityAuditQueryFailed):
        SecurityAuditQueryRunner(factory).run(
            "host=control", "host=reader", cursor
        )


def test_result_refuses_row_beyond_data_cut_or_not_live_through_intent_expiry():
    too_new = _pretenant_row(observed_at=DATA_CUT + timedelta(microseconds=1))
    old_observed_at = EXPIRES_AT - timedelta(seconds=RETENTION_SECONDS)
    expires_too_early = _pretenant_row(observed_at=old_observed_at)

    for row in (too_new, expires_too_early):
        factory, _, _ = _factory_for_rows([row])
        with pytest.raises(SecurityAuditQueryFailed):
            SecurityAuditQueryRunner(factory).run(
                "host=control", "host=reader", None
            )


def test_post_acknowledgement_close_failures_cannot_downgrade_report():
    factory, control, reader = _factory_for_rows(
        [_pretenant_row()],
        control_kwargs={"close_error": RuntimeError("control close")},
        reader_kwargs={"close_error": RuntimeError("reader close")},
    )

    acknowledged = SecurityAuditQueryRunner(factory).run(
        "host=control", "host=reader", None
    )

    assert control.commit_calls == 1
    assert control.close_calls == 1
    assert reader.close_calls == 1
    assert acknowledged.report_bytes.endswith(b"\n")


@pytest.mark.parametrize(
    "argv",
    (
        pytest.param(("-h",), id="short-help"),
        pytest.param(("--help",), id="long-help"),
        pytest.param(("--",), id="separator"),
        pytest.param(("--cursor",), id="missing-cursor"),
        pytest.param(("value",), id="positional"),
        pytest.param(("--cursor", "", "extra"), id="extra"),
        pytest.param(
            (
                "--cursor",
                "2026-08-13T10:20:30Z/" + str(EVENT_ID),
            ),
            id="noncanonical-cursor",
        ),
    ),
)
def test_cli_rejects_every_invalid_argument_shape_before_runner(argv):
    runner = _StubRunner(_acknowledged())

    code, output, error = _run_cli(runner, argv=argv)

    assert code == 2
    assert output.getvalue() == b""
    assert error.getvalue() == "security-audit query command is invalid\n"
    assert runner.calls == []


@pytest.mark.parametrize(
    "environ",
    (
        pytest.param({}, id="both-missing"),
        pytest.param(
            {READER_DSN_ENVIRONMENT: "host=reader"},
            id="control-missing",
        ),
        pytest.param(
            {
                CONTROL_DSN_ENVIRONMENT: "host=control",
                READER_DSN_ENVIRONMENT: "   ",
            },
            id="reader-whitespace",
        ),
        pytest.param(
            {
                CONTROL_DSN_ENVIRONMENT: "host=control",
                READER_DSN_ENVIRONMENT: "host='unterminated",
            },
            id="reader-malformed",
        ),
    ),
)
def test_cli_validates_both_conninfo_values_before_runner(environ):
    runner = _StubRunner(_acknowledged())

    code, output, error = _run_cli(runner, environ=environ)

    assert code == 2
    assert output.getvalue() == b""
    assert error.getvalue() == "security-audit query command is invalid\n"
    assert runner.calls == []


def test_cli_passes_one_parsed_cursor_and_writes_exact_report():
    runner = _StubRunner(_acknowledged())
    output = _RecordingOutput()
    cursor_text = (
        "2026-08-13T10:20:30.123456Z/"
        "11111111-1111-4111-8111-111111111111"
    )

    code, returned_output, error = _run_cli(
        runner,
        argv=("--cursor", cursor_text),
        stdout=output,
    )

    assert code == 0
    assert returned_output is output
    assert bytes(output.value) == REPORT_BYTES
    assert output.flush_calls == 1
    assert error.getvalue() == ""
    assert runner.calls == [
        (
            "host=control dbname=audit",
            "host=reader dbname=audit",
            SecurityAuditQueryCursor.parse(cursor_text),
        )
    ]


@pytest.mark.parametrize(
    ("outcome", "exit_code", "line"),
    (
        pytest.param(
            SecurityAuditQueryRefused("secret"),
            1,
            "security-audit query was refused\n",
            id="refused",
        ),
        pytest.param(
            SecurityAuditQueryControlUnavailable("secret"),
            3,
            "security-audit query control route is unavailable; "
            "no commit was sent\n",
            id="unavailable",
        ),
        pytest.param(
            SecurityAuditQueryOutcomeUnknown("secret"),
            4,
            "security-audit query access-intent outcome is unknown; "
            "no query was sent; do not retry automatically\n",
            id="unknown",
        ),
        pytest.param(
            SecurityAuditQueryFailed("secret"),
            5,
            "security-audit query intent committed but no complete report is "
            "available; do not retry automatically\n",
            id="query-failed",
        ),
    ),
)
def test_cli_failure_protocol_is_closed_and_secret_free(outcome, exit_code, line):
    runner = _StubRunner(outcome)

    code, output, error = _run_cli(runner)

    assert code == exit_code
    assert output.getvalue() == b""
    assert error.getvalue() == line
    assert "secret" not in error.getvalue()
    assert len(runner.calls) == 1


def test_cli_does_not_invent_state_for_nonconforming_runner_exception():
    runner = _StubRunner(RuntimeError("unexpected secret"))
    output = BytesIO()
    error = StringIO()

    with pytest.raises(RuntimeError, match="unexpected secret"):
        run_fixed_security_audit_query_cli(
            argv=(),
            environ={
                CONTROL_DSN_ENVIRONMENT: "host=control dbname=audit",
                READER_DSN_ENVIRONMENT: "host=reader dbname=audit",
            },
            stdout=output,
            stderr=error,
            runner=runner,
        )

    assert output.getvalue() == b""
    assert error.getvalue() == ""
    assert len(runner.calls) == 1


@pytest.mark.parametrize(
    ("output", "expected_prefix", "flush_calls"),
    (
        pytest.param(
            _RecordingOutput(short_write=True),
            REPORT_BYTES[:-1],
            0,
            id="short-write",
        ),
        pytest.param(
            _RecordingOutput(write_error=OSError("secret write")),
            b"",
            0,
            id="write-error",
        ),
        pytest.param(
            _RecordingOutput(flush_error=OSError("secret flush")),
            REPORT_BYTES,
            1,
            id="flush-error",
        ),
    ),
)
def test_cli_reporting_failure_is_exit_six_without_second_runner_call(
    output,
    expected_prefix,
    flush_calls,
):
    runner = _StubRunner(_acknowledged())

    code, returned_output, error = _run_cli(runner, stdout=output)

    assert code == 6
    assert returned_output is output
    assert bytes(output.value) == expected_prefix
    assert output.flush_calls == flush_calls
    assert error.getvalue() == (
        "security-audit query completed but reporting failed; "
        "do not retry automatically\n"
    )
    assert len(runner.calls) == 1


def test_operator_documentation_is_bounded_one_shot_and_claim_limited():
    documentation = (PACKAGE_ROOT / "deployment/postgresql/README.md").read_text()

    assert "python -m deployment.postgresql.run_security_audit_query" in documentation
    assert "commits one fixed `AUDIT_ACCESS` intent" in documentation
    assert "opens the reader route only after that commit is acknowledged" in documentation
    assert "at most 256 event rows" in documentation
    assert "must not retry exits `4`, `5`, or `6`" in documentation
    assert "not a deployment-readiness or external clock-fence claim" in documentation


def _access_event_count(state: dict[str, object]) -> int:
    with psycopg.connect(str(state["target_admin_dsn"])) as admin:
        return admin.execute(
            """
            SELECT pg_catalog.count(*)
            FROM ofarm_security.operational_security_event
            WHERE event_kind = 'AUDIT_ACCESS'
              AND access_purpose = %s
              AND access_function_identity = %s
              AND access_max_rows = %s
              AND access_max_bytes = %s
            """,
            (
                QUERY_ACCESS_PURPOSE_IDENTITY,
                QUERY_FUNCTION_IDENTITY,
                QUERY_MAX_ROWS,
                QUERY_MAX_BYTES,
            ),
        ).fetchone()[0]


def test_live_final_options_connect_both_roles_and_preserve_server_hard_bound(
    migrated_audit_service,
):
    state = migrated_audit_service
    hostile_options = (
        "-c statement_timeout=0 -c work_mem=64MB "
        "-c TimeZone=Europe/Ljubljana -c temp_file_limit=1024"
    )
    role_cases = (
        (
            "ofarm_security_audit_control_login",
            False,
            QUERY_CONTROL_CONNECTION_OPTIONS,
            "on",
        ),
        (
            "ofarm_security_audit_reader_login",
            True,
            QUERY_READER_CONNECTION_OPTIONS,
            "on",
        ),
    )

    for role, autocommit, options, expected_synchronous_commit in role_cases:
        hostile_dsn = psycopg.conninfo.make_conninfo(
            role_dsn(state, role),
            options=hostile_options,
        )
        with psycopg.connect(
            hostile_dsn,
            autocommit=autocommit,
            connect_timeout=QUERY_CONNECT_TIMEOUT_SECONDS,
            options=options,
        ) as connection:
            settings = connection.execute(
                """
                SELECT current_setting('statement_timeout'),
                       current_setting('lock_timeout'),
                       current_setting('idle_in_transaction_session_timeout'),
                       current_setting('transaction_timeout'),
                       current_setting('work_mem'),
                       current_setting('bytea_output'),
                       current_setting('TimeZone'),
                       current_setting('DateStyle'),
                       current_setting('temp_file_limit'),
                       current_setting('synchronous_commit')
                """
            ).fetchone()
        assert settings == (
            "5s",
            "500ms",
            "10s",
            "15s",
            "1MB",
            "hex",
            "UTC",
            "ISO, MDY",
            "0",
            expected_synchronous_commit,
        )


def test_live_wrong_control_role_refuses_without_access_intent(
    migrated_audit_service,
):
    state = migrated_audit_service
    before = _access_event_count(state)

    with pytest.raises(SecurityAuditQueryRefused):
        SecurityAuditQueryRunner().run(
            role_dsn(state, "ofarm_security_audit_reader_login"),
            role_dsn(state, "ofarm_security_audit_reader_login"),
            None,
        )

    assert _access_event_count(state) == before


def test_live_reader_failure_occurs_after_one_durable_access_intent(
    migrated_audit_service,
):
    state = migrated_audit_service
    before = _access_event_count(state)

    with pytest.raises(SecurityAuditQueryFailed):
        SecurityAuditQueryRunner().run(
            role_dsn(state, "ofarm_security_audit_control_login"),
            role_dsn(state, "ofarm_security_audit_control_login"),
            None,
        )

    assert _access_event_count(state) == before + 1


def test_live_reader_returns_fresh_events_with_canonical_cursor(
    migrated_audit_service,
):
    state = migrated_audit_service
    event_ids = (uuid4(), uuid4())
    with psycopg.connect(
        role_dsn(state, "ofarm_security_authentication_producer_login"),
        autocommit=True,
    ) as producer:
        for event_id in event_ids:
            producer.execute(
                """
                SELECT * FROM ofarm_security.append_pretenant_failure(
                    %s, 'CREDENTIAL_MISSING', %s,
                    'OFARM_PRETENANT_CORRELATION_V1', 2
                )
                """,
                (event_id, bytes(range(32))),
            )

    acknowledged = SecurityAuditQueryRunner().run(
        role_dsn(state, "ofarm_security_audit_control_login"),
        role_dsn(state, "ofarm_security_audit_reader_login"),
        None,
    )

    returned_ids = {event.event_id for event in acknowledged.events}
    assert set(event_ids) <= returned_ids
    assert 1 <= len(acknowledged.events) <= QUERY_MAX_ROWS
    assert acknowledged.next_cursor is not None
    assert acknowledged.report_bytes.endswith(b"\n")
    document = json.loads(acknowledged.report_bytes)
    assert document["returnedRowCount"] == len(acknowledged.events)
    assert document["nextCursor"] == acknowledged.next_cursor.render()


def test_live_valid_retired_historical_reasons_remain_queryable(
    migrated_audit_service,
):
    state = migrated_audit_service
    historical = (
        (
            uuid4(),
            "AUTHENTICATION_BOUNDARY_V1",
            "AUTHENTICATION",
            "TENANT_PARTY_PIN_REFUSED",
        ),
        (
            uuid4(),
            "REQUEST_ROUTER_BOUNDARY_V1",
            "REQUEST_ROUTER",
            "SECURITY_ROUTE_REFUSED",
        ),
    )
    with psycopg.connect(str(state["target_admin_dsn"])) as admin:
        observed_at = admin.execute(
            "SELECT pg_catalog.clock_timestamp() - interval '1 second'"
        ).fetchone()[0]
        for index, (event_id, producer, component, reason) in enumerate(historical):
            row_observed_at = observed_at - timedelta(microseconds=index)
            admin.execute(
                """
                INSERT INTO ofarm_security.operational_security_event (
                    event_id, event_insert_xid, observed_at, purge_after,
                    event_kind, producer, component, reason,
                    correlation_hmac_domain, correlation_hmac_key_version,
                    correlation_hmac_value, event_format_identity,
                    redaction_policy_identity, retention_policy_identity,
                    append_input_fingerprint
                ) VALUES (
                    %s, pg_catalog.pg_current_xact_id(), %s,
                    %s + pg_catalog.make_interval(secs => 2592000),
                    'PRE_TENANT_FAILURE', %s, %s, %s,
                    'OFARM_PRETENANT_CORRELATION_V1', 1, %s,
                    'OFARM_PRETENANT_SECURITY_EVENT_V1',
                    'CORRELATION_HMAC_ONLY_V1',
                    'SECURITY_DIAGNOSTIC_30D_V1', %s
                )
                """,
                (
                    event_id,
                    row_observed_at,
                    row_observed_at,
                    producer,
                    component,
                    reason,
                    bytes(range(32)),
                    bytes(reversed(range(32))),
                ),
            )

    acknowledged = SecurityAuditQueryRunner().run(
        role_dsn(state, "ofarm_security_audit_control_login"),
        role_dsn(state, "ofarm_security_audit_reader_login"),
        None,
    )

    returned = {
        event.event_id: event.reason
        for event in acknowledged.events
        if event.event_id in {item[0] for item in historical}
    }
    assert returned == {item[0]: item[3] for item in historical}
