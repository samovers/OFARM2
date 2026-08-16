"""Focused tests for library-only bounded security-audit export execution."""

from __future__ import annotations

import inspect
import json
import secrets
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import IsolationLevel, sql
from psycopg.pq import TransactionStatus

import deployment.postgresql.security_audit_export as export_module
from deployment.postgresql.audit_contract import (
    ACCESS_INTENT_EXPIRY_SECONDS,
    CORRELATION_HMAC_DOMAIN,
    EVENT_FORMAT_IDENTITY,
    EXPORT_ACCESS_PURPOSE_IDENTITY,
    EXPORT_FUNCTION_IDENTITY,
    EXPORT_MAX_BYTES,
    EXPORT_MAX_ROWS,
    REDACTION_POLICY_IDENTITY,
    RETENTION_POLICY_IDENTITY,
    RETENTION_SECONDS,
)
from deployment.postgresql.security_audit_access import SecurityAuditAccessCursor
from deployment.postgresql.security_audit_export import (
    AcknowledgedSecurityAuditExport,
    BOUNDED_EXPORT_SQL,
    EXPORT_ACCESS_INTENT_SQL,
    EXPORT_CONNECTION_OPTIONS,
    EXPORT_CONNECT_TIMEOUT_SECONDS,
    EXPORT_CONTROL_CONNECTION_OPTIONS,
    EXPORT_PAGE_SCHEMA,
    SecurityAuditExportControlUnavailable,
    SecurityAuditExportError,
    SecurityAuditExportFailed,
    SecurityAuditExportOutcomeUnknown,
    SecurityAuditExportRefused,
    SecurityAuditExportRunner,
)
from deployment.postgresql.security_audit_query import SecurityAuditQueryRunner
from kernel.tests.postgresql_audit_support import (
    audit_service_fixture,  # noqa: F401
    role_dsn,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
ACCESS_EVENT_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
DATA_CUT = datetime(2026, 8, 16, 10, 20, 30, 123456, tzinfo=timezone.utc)
EXPIRES_AT = DATA_CUT + timedelta(seconds=ACCESS_INTENT_EXPIRY_SECONDS)
EVENT_ID = UUID("11111111-1111-4111-8111-111111111111")
EVENT_AT = DATA_CUT - timedelta(seconds=10)
PURGE_AFTER = EVENT_AT + timedelta(seconds=RETENTION_SECONDS)
CONTROL_ROUTE = "host=control dbname=audit application_name='bounded export control'"
EXPORT_ROUTE = "host=export dbname=audit application_name='bounded export page'"
GOLDEN_PAGE_BYTES = (
    b'{"accessEventId":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",'
    b'"dataCut":"2026-08-16T10:20:30.123456Z","events":['
    b'{"accessCursorEventId":null,"accessCursorObservedAt":null,'
    b'"accessDataCut":null,"accessExpiresAt":null,'
    b'"accessFunctionIdentity":null,"accessMaxBytes":null,'
    b'"accessMaxRows":null,"accessPurpose":null,'
    b'"affectedComponent":null,"affectedProducer":null,'
    b'"appendInputFingerprint":"1f1e1d1c1b1a19181716151413121110'
    b'0f0e0d0c0b0a09080706050403020100","component":"AUTHENTICATION",'
    b'"correlationHmacDomain":"OFARM_PRETENANT_CORRELATION_V1",'
    b'"correlationHmacKeyVersion":1,"correlationHmacValue":"00010203'
    b'0405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f",'
    b'"eventFormatIdentity":"OFARM_PRETENANT_SECURITY_EVENT_V1",'
    b'"eventId":"11111111-1111-4111-8111-111111111111",'
    b'"eventKind":"PRE_TENANT_FAILURE","intervalCountUnknown":null,'
    b'"intervalEnd":null,"intervalEventCount":null,"intervalStart":null,'
    b'"observedAt":"2026-08-16T10:20:20.123456Z",'
    b'"producer":"AUTHENTICATION_BOUNDARY_V1",'
    b'"purgeAfter":"2026-09-15T10:20:20.123456Z",'
    b'"reason":"TENANT_PARTY_PIN_REFUSED",'
    b'"redactionPolicyIdentity":"CORRELATION_HMAC_ONLY_V1",'
    b'"retentionCutoff":null,"retentionDeletedCount":null,'
    b'"retentionPolicyIdentity":"SECURITY_DIAGNOSTIC_30D_V1"}],'
    b'"expiresAt":"2026-08-16T10:25:30.123456Z",'
    b'"functionIdentity":"ofarm_security.export_operational_security_events'
    b'(uuid, timestamptz, uuid, integer, bigint)","inputCursor":null,'
    b'"maxBytes":8388608,"maxRows":2048,'
    b'"nextCursor":"2026-08-16T10:20:20.123456Z/'
    b'11111111-1111-4111-8111-111111111111","outcome":"ACKNOWLEDGED",'
    b'"purpose":"DUAL_APPROVED_BREAK_GLASS_EXPORT_V1",'
    b'"returnedRowCount":1,'
    b'"schemaVersion":"ofarm.security-audit-bounded-export-page.v1"}\n'
)


def _intent_row() -> tuple[object, ...]:
    return ACCESS_EVENT_ID, DATA_CUT, EXPIRES_AT


def _pretenant_row(
    *,
    event_id: UUID = EVENT_ID,
    observed_at: datetime = EVENT_AT,
    producer: str = "AUTHENTICATION_BOUNDARY_V1",
    component: str = "AUTHENTICATION",
    reason: str = "CREDENTIAL_MISSING",
    hmac_key_version: int = 1,
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
        hmac_key_version,
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
    values = list(_pretenant_row())
    values[3] = event_kind
    values[4] = "SECURITY_OPERATIONS_V1"
    values[5] = (
        "AUDIT_RETENTION" if event_kind == "AUDIT_RETENTION" else "AUDIT_CONTROL"
    )
    values[6:10] = [None, None, None, None]
    if event_kind == "AUDIT_ACCESS":
        values[14:22] = [
            EXPORT_ACCESS_PURPOSE_IDENTITY,
            EXPORT_FUNCTION_IDENTITY,
            EVENT_AT,
            None,
            None,
            EXPORT_MAX_ROWS,
            EXPORT_MAX_BYTES,
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
        rollback_error: Exception | None = None,
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
        self._rollback_error = rollback_error
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

    def execute(self, query: str, params: tuple[object, ...]) -> _FakeCursor:
        self.executed.append((query, params))
        if self._execute_error is not None:
            raise self._execute_error
        return self.cursor

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


def _factory_for_rows(
    rows: list[object],
    *,
    control_kwargs: dict[str, object] | None = None,
    export_kwargs: dict[str, object] | None = None,
    control_rows: list[object] | None = None,
) -> tuple[_FakeFactory, _FakeConnection, _FakeConnection]:
    control = _FakeConnection(
        [_intent_row()] if control_rows is None else control_rows,
        autocommit=False,
        **(control_kwargs or {}),
    )
    exporter = _FakeConnection(
        rows,
        autocommit=True,
        **(export_kwargs or {}),
    )
    return _FakeFactory([control, exporter]), control, exporter


def _assert_fixed_error(
    error: BaseException,
    expected: type[SecurityAuditExportError],
    canaries: tuple[str, ...] = (),
) -> None:
    assert type(error) is expected
    assert error.args == ()
    assert str(error) == ""
    assert error.__cause__ is None
    assert error.__context__ is None
    formatted = "".join(
        traceback.TracebackException.from_exception(
            error, capture_locals=False
        ).format()
    )
    for canary in canaries:
        assert canary not in formatted


def test_export_error_classes_are_one_exact_closed_family():
    assert SecurityAuditExportError.__bases__ == (RuntimeError,)
    for error_type in (
        SecurityAuditExportRefused,
        SecurityAuditExportControlUnavailable,
        SecurityAuditExportOutcomeUnknown,
        SecurityAuditExportFailed,
    ):
        assert error_type.__bases__ == (SecurityAuditExportError,)


def test_runner_api_has_no_protocol_limit_role_or_access_id_inputs():
    assert tuple(inspect.signature(SecurityAuditExportRunner.run).parameters) == (
        "self",
        "control_conninfo",
        "export_conninfo",
        "cursor",
    )


@pytest.mark.parametrize(
    ("control_conninfo", "export_conninfo", "cursor"),
    (
        pytest.param(None, EXPORT_ROUTE, None, id="control-non-string"),
        pytest.param("   ", EXPORT_ROUTE, None, id="control-blank"),
        pytest.param("host='unterminated", EXPORT_ROUTE, None, id="control-malformed"),
        pytest.param(CONTROL_ROUTE, None, None, id="export-non-string"),
        pytest.param(CONTROL_ROUTE, "\t", None, id="export-blank"),
        pytest.param(CONTROL_ROUTE, "host='unterminated", None, id="export-malformed"),
        pytest.param(CONTROL_ROUTE, EXPORT_ROUTE, object(), id="cursor-unvalidated"),
    ),
)
def test_complete_route_preflight_refuses_before_every_factory_call(
    control_conninfo,
    export_conninfo,
    cursor,
):
    factory = _FakeFactory([])

    with pytest.raises(SecurityAuditExportRefused) as refused:
        SecurityAuditExportRunner(factory).run(
            control_conninfo,
            export_conninfo,
            cursor,
        )

    _assert_fixed_error(refused.value, SecurityAuditExportRefused)
    assert factory.calls == []


def test_runner_passes_original_routes_and_one_cursor_to_exact_fixed_calls(
    monkeypatch,
):
    control_route = (
        "host=control dbname=audit password=control-canary "
        "options='-c statement_timeout=0 -c TimeZone=Europe/Ljubljana'"
    )
    export_route = (
        "host=export dbname=audit password=export-canary "
        "options='-c work_mem=64MB -c bytea_output=escape'"
    )
    cursor = SecurityAuditAccessCursor(
        observed_at=DATA_CUT,
        event_id=UUID("22222222-2222-4222-8222-222222222222"),
    )
    factory, control, exporter = _factory_for_rows([])
    parsed_routes: list[str] = []
    real_parser = psycopg.conninfo.conninfo_to_dict

    def record_parse(value: str):
        parsed_routes.append(value)
        return real_parser(value)

    monkeypatch.setattr(psycopg.conninfo, "conninfo_to_dict", record_parse)

    acknowledged = SecurityAuditExportRunner(factory).run(
        control_route,
        export_route,
        cursor,
    )

    assert isinstance(acknowledged, AcknowledgedSecurityAuditExport)
    assert acknowledged.input_cursor is cursor
    assert parsed_routes == [control_route, export_route]
    assert factory.calls == [
        (
            control_route,
            False,
            EXPORT_CONNECT_TIMEOUT_SECONDS,
            EXPORT_CONTROL_CONNECTION_OPTIONS,
        ),
        (
            export_route,
            True,
            EXPORT_CONNECT_TIMEOUT_SECONDS,
            EXPORT_CONNECTION_OPTIONS,
        ),
    ]
    assert control.executed == [
        (
            EXPORT_ACCESS_INTENT_SQL,
            (
                EXPORT_ACCESS_PURPOSE_IDENTITY,
                EXPORT_FUNCTION_IDENTITY,
                cursor.observed_at,
                cursor.event_id,
                EXPORT_MAX_ROWS,
                EXPORT_MAX_BYTES,
            ),
        )
    ]
    assert control.isolation_level is IsolationLevel.READ_COMMITTED
    assert control.commit_calls == 1
    assert exporter.executed == [
        (
            BOUNDED_EXPORT_SQL,
            (
                ACCESS_EVENT_ID,
                cursor.observed_at,
                cursor.event_id,
                EXPORT_MAX_ROWS,
                EXPORT_MAX_BYTES,
            ),
        )
    ]
    assert exporter.cursor.fetchmany_sizes == [EXPORT_MAX_ROWS + 1]
    assert control.close_calls == 1
    assert exporter.close_calls == 1


def test_canonical_export_page_uses_the_normal_readers_exact_event_document():
    row = _pretenant_row(reason="TENANT_PARTY_PIN_REFUSED")
    export_factory, _, _ = _factory_for_rows([row])
    query_factory, _, _ = _factory_for_rows([row])

    exported = SecurityAuditExportRunner(export_factory).run(
        CONTROL_ROUTE,
        EXPORT_ROUTE,
        None,
    )
    queried = SecurityAuditQueryRunner(query_factory).run(
        CONTROL_ROUTE,
        EXPORT_ROUTE,
        None,
    )

    export_document = json.loads(exported.page_bytes)
    query_document = json.loads(queried.report_bytes)
    assert export_document["events"] == query_document["events"]
    assert set(export_document) == {
        "accessEventId",
        "dataCut",
        "events",
        "expiresAt",
        "functionIdentity",
        "inputCursor",
        "maxBytes",
        "maxRows",
        "nextCursor",
        "outcome",
        "purpose",
        "returnedRowCount",
        "schemaVersion",
    }
    assert export_document == {
        "accessEventId": str(ACCESS_EVENT_ID),
        "dataCut": "2026-08-16T10:20:30.123456Z",
        "events": query_document["events"],
        "expiresAt": "2026-08-16T10:25:30.123456Z",
        "functionIdentity": EXPORT_FUNCTION_IDENTITY,
        "inputCursor": None,
        "maxBytes": EXPORT_MAX_BYTES,
        "maxRows": EXPORT_MAX_ROWS,
        "nextCursor": "2026-08-16T10:20:20.123456Z/" + str(EVENT_ID),
        "outcome": "ACKNOWLEDGED",
        "purpose": EXPORT_ACCESS_PURPOSE_IDENTITY,
        "returnedRowCount": 1,
        "schemaVersion": EXPORT_PAGE_SCHEMA,
    }
    assert exported.page_bytes == GOLDEN_PAGE_BYTES
    assert exported.page_bytes == (
        json.dumps(
            export_document,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        + b"\n"
    )
    assert exported.page_bytes.isascii()
    assert exported.page_bytes.endswith(b"\n")
    assert not exported.page_bytes.endswith(b"\n\n")


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
def test_export_accepts_every_shared_maintenance_event_shape(event_kind):
    factory, _, _ = _factory_for_rows([_maintenance_row(event_kind)])

    acknowledged = SecurityAuditExportRunner(factory).run(
        CONTROL_ROUTE,
        EXPORT_ROUTE,
        None,
    )

    assert acknowledged.events[0].event_kind == event_kind


def test_retired_closed_history_is_preserved_but_unknown_read_sets_are_refused():
    historical = _pretenant_row(
        producer="REQUEST_ROUTER_BOUNDARY_V1",
        component="REQUEST_ROUTER",
        reason="SECURITY_ROUTE_REFUSED",
        hmac_key_version=1,
    )
    factory, _, _ = _factory_for_rows([historical])

    acknowledged = SecurityAuditExportRunner(factory).run(
        CONTROL_ROUTE,
        EXPORT_ROUTE,
        None,
    )

    assert acknowledged.events[0].reason == "SECURITY_ROUTE_REFUSED"
    for refused_row in (
        _replace(historical, 4, "UNKNOWN_PRODUCER"),
        _replace(historical, 8, 99),
        _replace(historical, 6, 'CREDENTIAL_"LEAK'),
        _replace(historical, 6, "CREDENTIAL\nLEAK"),
    ):
        refused_factory, _, _ = _factory_for_rows([refused_row])
        with pytest.raises(SecurityAuditExportFailed):
            SecurityAuditExportRunner(refused_factory).run(
                CONTROL_ROUTE,
                EXPORT_ROUTE,
                None,
            )


@pytest.mark.parametrize(
    "row",
    (
        pytest.param(list(_pretenant_row()), id="non-tuple"),
        pytest.param(_pretenant_row()[:-1], id="short-carrier"),
        pytest.param(_replace(_pretenant_row(), 0, UUID(int=0)), id="nil-id"),
        pytest.param(
            _replace(_pretenant_row(), 1, EVENT_AT.replace(tzinfo=None)),
            id="naive-time",
        ),
        pytest.param(
            _replace(_pretenant_row(), 2, PURGE_AFTER + timedelta(microseconds=1)),
            id="wrong-retention",
        ),
        pytest.param(_replace(_pretenant_row(), 3, "UNKNOWN"), id="unknown-kind"),
        pytest.param(_replace(_pretenant_row(), 9, bytes(31)), id="short-hmac"),
        pytest.param(
            _replace(_pretenant_row(), 13, bytes(31)),
            id="short-fingerprint",
        ),
        pytest.param(
            _replace(_pretenant_row(), 14, EXPORT_ACCESS_PURPOSE_IDENTITY),
            id="unexpected-extension",
        ),
    ),
)
def test_malformed_shared_carrier_never_returns_an_export_page(row):
    factory, control, exporter = _factory_for_rows([row])

    with pytest.raises(SecurityAuditExportFailed):
        SecurityAuditExportRunner(factory).run(
            CONTROL_ROUTE,
            EXPORT_ROUTE,
            None,
        )

    assert control.commit_calls == 1
    assert exporter.close_calls == 1


def test_export_refuses_the_2049th_row_without_fetch_loop_or_continuation():
    rows = [
        _pretenant_row(
            event_id=UUID(int=index + 1),
            observed_at=EVENT_AT - timedelta(microseconds=index),
        )
        for index in range(EXPORT_MAX_ROWS + 1)
    ]
    factory, control, exporter = _factory_for_rows(rows)

    with pytest.raises(SecurityAuditExportFailed):
        SecurityAuditExportRunner(factory).run(
            CONTROL_ROUTE,
            EXPORT_ROUTE,
            None,
        )

    assert control.commit_calls == 1
    assert len(exporter.executed) == 1
    assert exporter.cursor.fetchmany_sizes == [EXPORT_MAX_ROWS + 1]
    assert len(factory.calls) == 2


@pytest.mark.parametrize(
    "rows",
    (
        pytest.param(
            [
                _pretenant_row(),
                _pretenant_row(
                    event_id=UUID("ffffffff-ffff-4fff-8fff-ffffffffffff"),
                    observed_at=EVENT_AT + timedelta(microseconds=1),
                ),
            ],
            id="ascending",
        ),
        pytest.param(
            [_pretenant_row(observed_at=DATA_CUT + timedelta(microseconds=1))],
            id="after-cut",
        ),
        pytest.param(
            [
                _pretenant_row(
                    observed_at=EXPIRES_AT - timedelta(seconds=RETENTION_SECONDS)
                )
            ],
            id="not-live-through-expiry",
        ),
    ),
)
def test_order_cut_and_expiry_violations_fail_after_acknowledged_intent(rows):
    factory, control, _ = _factory_for_rows(rows)

    with pytest.raises(SecurityAuditExportFailed):
        SecurityAuditExportRunner(factory).run(
            CONTROL_ROUTE,
            EXPORT_ROUTE,
            None,
        )

    assert control.commit_calls == 1


def test_row_at_the_input_cursor_is_refused():
    cursor = SecurityAuditAccessCursor(EVENT_AT, EVENT_ID)
    factory, _, _ = _factory_for_rows([_pretenant_row()])

    with pytest.raises(SecurityAuditExportFailed):
        SecurityAuditExportRunner(factory).run(
            CONTROL_ROUTE,
            EXPORT_ROUTE,
            cursor,
        )


def test_control_factory_failure_is_unavailable_without_retry():
    factory = _FakeFactory([RuntimeError("dependency-control-canary")])

    with pytest.raises(SecurityAuditExportControlUnavailable) as unavailable:
        SecurityAuditExportRunner(factory).run(CONTROL_ROUTE, EXPORT_ROUTE, None)

    _assert_fixed_error(
        unavailable.value,
        SecurityAuditExportControlUnavailable,
        ("dependency-control-canary",),
    )
    assert len(factory.calls) == 1


@pytest.mark.parametrize(
    ("control_kwargs", "canaries"),
    (
        pytest.param({"closed": True}, (), id="closed"),
        pytest.param(
            {"transaction_status": TransactionStatus.ACTIVE}, (), id="active"
        ),
        pytest.param(
            {"isolation_error": RuntimeError("isolation-canary")},
            ("isolation-canary",),
            id="isolation",
        ),
        pytest.param(
            {
                "execute_error": RuntimeError("intent-execute-canary"),
                "rollback_error": RuntimeError("rollback-canary"),
                "close_error": RuntimeError("precommit-close-canary"),
            },
            (
                "intent-execute-canary",
                "rollback-canary",
                "precommit-close-canary",
            ),
            id="execute",
        ),
    ),
)
def test_precommit_control_failure_rolls_back_closes_and_never_opens_export(
    control_kwargs,
    canaries,
):
    factory, control, _ = _factory_for_rows([], control_kwargs=control_kwargs)

    with pytest.raises(SecurityAuditExportRefused) as refused:
        SecurityAuditExportRunner(factory).run(CONTROL_ROUTE, EXPORT_ROUTE, None)

    _assert_fixed_error(
        refused.value,
        SecurityAuditExportRefused,
        canaries,
    )
    assert control.rollback_calls == 1
    assert control.commit_calls == 0
    assert control.close_calls == 1
    assert len(factory.calls) == 1


@pytest.mark.parametrize(
    "control_rows",
    (
        pytest.param([], id="missing"),
        pytest.param([_intent_row(), _intent_row()], id="second-row"),
        pytest.param([(UUID(int=0), DATA_CUT, EXPIRES_AT)], id="nil-id"),
        pytest.param(
            [(ACCESS_EVENT_ID, DATA_CUT, EXPIRES_AT + timedelta(seconds=1))],
            id="wrong-duration",
        ),
    ),
)
def test_invalid_intent_result_refuses_before_commit_or_export(control_rows):
    factory, control, _ = _factory_for_rows([], control_rows=control_rows)

    with pytest.raises(SecurityAuditExportRefused):
        SecurityAuditExportRunner(factory).run(CONTROL_ROUTE, EXPORT_ROUTE, None)

    assert control.rollback_calls == 1
    assert control.commit_calls == 0
    assert len(factory.calls) == 1


def test_explicit_commit_exception_is_unknown_and_never_opens_export():
    factory, control, _ = _factory_for_rows(
        [],
        control_kwargs={
            "commit_error": RuntimeError("commit-secret-canary"),
            "close_error": RuntimeError("unknown-close-canary"),
        },
    )

    with pytest.raises(SecurityAuditExportOutcomeUnknown) as unknown:
        SecurityAuditExportRunner(factory).run(CONTROL_ROUTE, EXPORT_ROUTE, None)

    _assert_fixed_error(
        unknown.value,
        SecurityAuditExportOutcomeUnknown,
        ("commit-secret-canary", "unknown-close-canary"),
    )
    assert control.commit_calls == 1
    assert control.close_calls == 1
    assert len(factory.calls) == 1


def test_export_factory_failure_occurs_only_after_acknowledged_intent():
    control = _FakeConnection([_intent_row()], autocommit=False)
    factory = _FakeFactory([control, RuntimeError("export-connect-canary")])

    with pytest.raises(SecurityAuditExportFailed) as failed:
        SecurityAuditExportRunner(factory).run(CONTROL_ROUTE, EXPORT_ROUTE, None)

    _assert_fixed_error(
        failed.value,
        SecurityAuditExportFailed,
        ("export-connect-canary",),
    )
    assert control.commit_calls == 1
    assert len(factory.calls) == 2


@pytest.mark.parametrize(
    ("export_kwargs", "canaries"),
    (
        pytest.param({"closed": True}, (), id="closed"),
        pytest.param(
            {"transaction_status": TransactionStatus.ACTIVE}, (), id="active"
        ),
        pytest.param(
            {
                "execute_error": RuntimeError("export-execute-canary"),
                "close_error": RuntimeError("failed-close-canary"),
            },
            ("export-execute-canary", "failed-close-canary"),
            id="execute",
        ),
        pytest.param(
            {"fetchmany_error": RuntimeError("export-fetch-canary")},
            ("export-fetch-canary",),
            id="fetch",
        ),
    ),
)
def test_post_intent_export_failure_closes_without_retry(export_kwargs, canaries):
    factory, control, exporter = _factory_for_rows(
        [_pretenant_row()],
        export_kwargs=export_kwargs,
    )

    with pytest.raises(SecurityAuditExportFailed) as failed:
        SecurityAuditExportRunner(factory).run(CONTROL_ROUTE, EXPORT_ROUTE, None)

    _assert_fixed_error(
        failed.value,
        SecurityAuditExportFailed,
        canaries,
    )
    assert control.commit_calls == 1
    assert exporter.close_calls == 1
    assert len(factory.calls) == 2
    assert len(exporter.executed) <= 1


def test_render_failure_is_detached_and_never_returns_a_partial_page(monkeypatch):
    canaries = (
        "control-password-runtime-canary",
        "export-password-runtime-canary",
        "page-render-runtime-canary",
        str(ACCESS_EVENT_ID),
        str(EVENT_ID),
    )
    control_route = "host=control password=" + canaries[0]
    export_route = "host=export password=" + canaries[1]
    factory, control, exporter = _factory_for_rows([_pretenant_row()])

    def fail_render(*_args, **_kwargs):
        raise RuntimeError(canaries[2])

    monkeypatch.setattr(export_module, "_render_page", fail_render)
    with pytest.raises(SecurityAuditExportFailed) as failed:
        SecurityAuditExportRunner(factory).run(
            control_route,
            export_route,
            None,
        )

    _assert_fixed_error(failed.value, SecurityAuditExportFailed, canaries)
    assert control.commit_calls == 1
    assert exporter.close_calls == 1


def test_every_outward_failure_is_fresh_and_unlinked_from_preflight_dependency():
    errors: list[SecurityAuditExportRefused] = []
    for _attempt in range(2):
        with pytest.raises(SecurityAuditExportRefused) as refused:
            SecurityAuditExportRunner(_FakeFactory([])).run(
                CONTROL_ROUTE,
                "host='runtime-route-canary",
                None,
            )
        errors.append(refused.value)
        _assert_fixed_error(
            refused.value,
            SecurityAuditExportRefused,
            ("runtime-route-canary",),
        )
    assert errors[0] is not errors[1]


class _StopNow(BaseException):
    pass


@pytest.mark.parametrize("stage", ("control", "intent", "commit", "export", "fetch"))
def test_base_exception_is_propagated_without_becoming_a_closed_outcome(stage):
    stop = _StopNow(stage)
    if stage == "control":
        factory = _FakeFactory([stop])
    elif stage == "intent":
        factory, _, _ = _factory_for_rows(
            [], control_kwargs={"execute_error": stop}
        )
    elif stage == "commit":
        factory, _, _ = _factory_for_rows(
            [], control_kwargs={"commit_error": stop}
        )
    elif stage == "export":
        control = _FakeConnection([_intent_row()], autocommit=False)
        factory = _FakeFactory([control, stop])
    else:
        factory, _, _ = _factory_for_rows(
            [_pretenant_row()], export_kwargs={"fetchmany_error": stop}
        )

    with pytest.raises(_StopNow) as propagated:
        SecurityAuditExportRunner(factory).run(CONTROL_ROUTE, EXPORT_ROUTE, None)

    assert propagated.value is stop


def test_post_acknowledgement_close_failures_cannot_downgrade_the_page():
    factory, control, exporter = _factory_for_rows(
        [_pretenant_row()],
        control_kwargs={"close_error": RuntimeError("control-close")},
        export_kwargs={"close_error": RuntimeError("export-close")},
    )

    acknowledged = SecurityAuditExportRunner(factory).run(
        CONTROL_ROUTE,
        EXPORT_ROUTE,
        None,
    )

    assert control.commit_calls == 1
    assert control.close_calls == 1
    assert exporter.close_calls == 1
    assert acknowledged.page_bytes.endswith(b"\n")


def test_modules_have_no_executable_adapter_or_protected_error_collector():
    access_source = (
        PACKAGE_ROOT / "deployment/postgresql/security_audit_access.py"
    ).read_text()
    export_source = (
        PACKAGE_ROOT / "deployment/postgresql/security_audit_export.py"
    ).read_text()
    combined = access_source + export_source

    assert "import traceback" not in combined
    assert "import logging" not in combined
    assert "TracebackException" not in combined
    assert "__main__" not in export_source
    assert not (
        PACKAGE_ROOT / "deployment/postgresql/run_security_audit_export.py"
    ).exists()


def test_documentation_is_library_only_and_claim_limited():
    documentation = " ".join(
        (PACKAGE_ROOT / "deployment/postgresql/README.md").read_text().split()
    )

    assert "bounded export-page library primitive" in documentation
    assert "at most 2,048 event rows" in documentation
    assert (
        "does not create or receive a separate temporary export credential parameter"
        in documentation
    )
    assert (
        "credential may be present inside the supplied export conninfo"
        in documentation
    )
    assert "no standalone export command" in documentation
    assert "does not prove dual approval" in documentation


def _structure(state: dict[str, object]) -> tuple[object, ...]:
    with psycopg.connect(
        role_dsn(state, "ofarm_security_audit_readiness_login"),
        autocommit=True,
    ) as readiness:
        return readiness.execute(
            "SELECT * FROM ofarm_security.verify_security_audit_structure()"
        ).fetchone()


@pytest.fixture(scope="module")
def temporary_export_route(migrated_audit_service):
    state = migrated_audit_service
    export_role = "ofarm_security_audit_export_login"
    export_password = "issue-192-export-" + secrets.token_urlsafe(32)
    assert _structure(state) == (True, 0, False)
    with psycopg.connect(str(state["admin_dsn"]), autocommit=True) as admin:
        admin.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                sql.Identifier(export_role),
                sql.Literal(export_password),
            )
        )
        admin.execute(
            """
            GRANT ofarm_security_audit_export
            TO ofarm_security_audit_export_login
            WITH INHERIT TRUE, SET FALSE, ADMIN FALSE
            """
        )
    try:
        incompatible = _structure(state)
        assert incompatible[0] is False
        assert incompatible[1] >= 1
        assert incompatible[2] is True
        yield psycopg.conninfo.make_conninfo(
            str(state["target_admin_dsn"]),
            user=export_role,
            password=export_password,
        )
    finally:
        with psycopg.connect(str(state["admin_dsn"]), autocommit=True) as admin:
            admin.execute(
                "DROP ROLE IF EXISTS ofarm_security_audit_export_login"
            )
        assert _structure(state) == (True, 0, False)


def _set_access_clock_high_water(
    state: dict[str, object], observed_at: datetime | None
) -> int:
    with psycopg.connect(str(state["target_admin_dsn"]), autocommit=True) as admin:
        high_water = admin.execute(
            """
            SELECT pg_catalog.floor(
                EXTRACT(EPOCH FROM COALESCE(
                    %s::pg_catalog.timestamptz,
                    pg_catalog.clock_timestamp()
                )) * 1000000
            )::pg_catalog.int8
            """,
            (observed_at,),
        ).fetchone()[0]
        admin.execute(
            """
            SELECT pg_catalog.setval(
                'ofarm_security.operational_security_access_clock_high_water'::
                    pg_catalog.regclass,
                %s,
                true
            )
            """,
            (high_water,),
        )
    return high_water


def test_live_export_runner_uses_fixed_options_and_returns_one_page(
    migrated_audit_service,
    temporary_export_route,
):
    state = migrated_audit_service
    event_id = uuid4()
    with psycopg.connect(
        role_dsn(state, "ofarm_security_authentication_producer_login"),
        autocommit=True,
    ) as producer:
        producer.execute(
            """
            SELECT * FROM ofarm_security.append_pretenant_failure(
                %s, 'CREDENTIAL_MISSING', %s,
                'OFARM_PRETENANT_CORRELATION_V1', 2
            )
            """,
            (event_id, bytes(range(32))),
        )

    hostile_control = psycopg.conninfo.make_conninfo(
        role_dsn(state, "ofarm_security_audit_control_login"),
        options="-c statement_timeout=0 -c TimeZone=Europe/Ljubljana",
    )
    hostile_export = psycopg.conninfo.make_conninfo(
        temporary_export_route,
        options="-c work_mem=64MB -c bytea_output=escape",
    )
    acknowledged = SecurityAuditExportRunner().run(
        hostile_control,
        hostile_export,
        None,
    )

    assert event_id in {event.event_id for event in acknowledged.events}
    assert 1 <= len(acknowledged.events) <= EXPORT_MAX_ROWS
    assert acknowledged.next_cursor is not None
    document = json.loads(acknowledged.page_bytes)
    assert document["returnedRowCount"] == len(acknowledged.events)
    assert document["nextCursor"] == acknowledged.next_cursor.render()

    route_cases = (
        (hostile_control, False, EXPORT_CONTROL_CONNECTION_OPTIONS, "on"),
        (hostile_export, True, EXPORT_CONNECTION_OPTIONS, "on"),
    )
    for conninfo, autocommit, options, expected_sync in route_cases:
        with psycopg.connect(
            conninfo,
            autocommit=autocommit,
            connect_timeout=EXPORT_CONNECT_TIMEOUT_SECONDS,
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
            expected_sync,
        )


def test_live_database_role_separation_remains_authoritative(
    migrated_audit_service,
    temporary_export_route,
):
    state = migrated_audit_service
    with pytest.raises(SecurityAuditExportRefused):
        SecurityAuditExportRunner().run(
            temporary_export_route,
            temporary_export_route,
            None,
        )
    with pytest.raises(SecurityAuditExportFailed):
        SecurityAuditExportRunner().run(
            role_dsn(state, "ofarm_security_audit_control_login"),
            role_dsn(state, "ofarm_security_audit_reader_login"),
            None,
        )


def test_live_database_exercises_equal_replay_mismatch_and_widening(
    migrated_audit_service,
    temporary_export_route,
):
    state = migrated_audit_service
    acknowledged = SecurityAuditExportRunner().run(
        role_dsn(state, "ofarm_security_audit_control_login"),
        temporary_export_route,
        None,
    )
    arguments = (
        acknowledged.intent.access_event_id,
        None,
        None,
        EXPORT_MAX_ROWS,
        EXPORT_MAX_BYTES,
    )
    with psycopg.connect(temporary_export_route, autocommit=True) as exporter:
        first_replay = exporter.execute(BOUNDED_EXPORT_SQL, arguments).fetchall()
        second_replay = exporter.execute(BOUNDED_EXPORT_SQL, arguments).fetchall()
        assert first_replay == second_replay

        with pytest.raises(psycopg.Error) as mismatch:
            exporter.execute(
                BOUNDED_EXPORT_SQL,
                (
                    acknowledged.intent.access_event_id,
                    DATA_CUT,
                    EVENT_ID,
                    EXPORT_MAX_ROWS,
                    EXPORT_MAX_BYTES,
                ),
            ).fetchall()
        assert mismatch.value.sqlstate == "42501"

        with pytest.raises(psycopg.Error) as widened_rows:
            exporter.execute(
                BOUNDED_EXPORT_SQL,
                (
                    acknowledged.intent.access_event_id,
                    None,
                    None,
                    EXPORT_MAX_ROWS + 1,
                    EXPORT_MAX_BYTES,
                ),
            ).fetchall()
        assert widened_rows.value.sqlstate == "22023"

        with pytest.raises(psycopg.Error) as widened_bytes:
            exporter.execute(
                BOUNDED_EXPORT_SQL,
                (
                    acknowledged.intent.access_event_id,
                    None,
                    None,
                    EXPORT_MAX_ROWS,
                    EXPORT_MAX_BYTES + 1,
                ),
            ).fetchall()
        assert widened_bytes.value.sqlstate == "22023"


def test_live_expired_export_intent_is_refused_and_clock_is_restored(
    migrated_audit_service,
    temporary_export_route,
):
    state = migrated_audit_service
    with psycopg.connect(
        role_dsn(state, "ofarm_security_audit_control_login"),
        autocommit=True,
    ) as control:
        access = control.execute(
            EXPORT_ACCESS_INTENT_SQL,
            (
                EXPORT_ACCESS_PURPOSE_IDENTITY,
                EXPORT_FUNCTION_IDENTITY,
                None,
                None,
                EXPORT_MAX_ROWS,
                EXPORT_MAX_BYTES,
            ),
        ).fetchone()

    _set_access_clock_high_water(state, access[2])
    try:
        with psycopg.connect(temporary_export_route, autocommit=True) as exporter:
            for _attempt in range(2):
                with pytest.raises(psycopg.Error) as expired:
                    exporter.execute(
                        BOUNDED_EXPORT_SQL,
                        (
                            access[0],
                            None,
                            None,
                            EXPORT_MAX_ROWS,
                            EXPORT_MAX_BYTES,
                        ),
                    ).fetchall()
                assert expired.value.sqlstate == "42501"
    finally:
        _set_access_clock_high_water(state, None)
