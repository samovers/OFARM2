"""Focused tests for bounded live security-audit gap reconciliation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Barrier, Event, Lock, Thread
from uuid import uuid4

import pytest
from psycopg import IsolationLevel
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.pq import TransactionStatus

from kernel import security_audit_gap as gap
from kernel.security_audit import (
    OverflowAuditAppend,
    OverflowBucket,
    SecurityAuditOutcomeUnknown,
    SecurityAuditRefused,
    SecurityAuditUnavailable,
    StoredAuditAppend,
)
from kernel.security_audit_gap import (
    SecurityAuditGapClient,
    SecurityAuditGapController,
    SecurityAuditGapOutcomeUnknown,
    SecurityAuditGapState,
    SecurityAuditGapUnavailable,
)


NOW = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)


def _stored(at: datetime = NOW + timedelta(seconds=10)) -> StoredAuditAppend:
    return StoredAuditAppend(uuid4(), at, at + timedelta(days=30))


def _overflow(at: datetime) -> OverflowAuditAppend:
    return OverflowAuditAppend(
        uuid4(),
        OverflowBucket("AUTHENTICATION_BOUNDARY_V1", "AUTHENTICATION", at),
        False,
    )


class _Client:
    def __init__(self, *, anchor=NOW, outcomes=()):
        self.anchor = anchor
        self.outcomes = list(outcomes)
        self.initialize_calls = 0
        self.calls = []

    def initialize(self):
        self.initialize_calls += 1
        if isinstance(self.anchor, BaseException):
            raise self.anchor
        return self.anchor

    def append(self, snapshot):
        self.calls.append(snapshot)
        outcome = (
            self.outcomes.pop(0)
            if self.outcomes
            else NOW + timedelta(seconds=30)
        )
        if isinstance(outcome, BaseException):
            raise outcome
        if callable(outcome):
            return outcome(snapshot)
        return outcome


class _Sink:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self._lock = Lock()
        self.calls = []

    def append(self, reason):
        with self._lock:
            self.calls.append(reason)
            outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        if callable(outcome):
            return outcome()
        return outcome


@pytest.mark.parametrize(
    ("error_type", "message"),
    (
        (
            SecurityAuditGapUnavailable,
            "security audit gap reconciliation is unavailable",
        ),
        (
            SecurityAuditGapOutcomeUnknown,
            "security audit gap reconciliation outcome is unknown",
        ),
    ),
)
def test_fixed_errors_have_exact_non_sensitive_surface(error_type, message):
    error = error_type()

    assert type(error) is error_type
    assert str(error) == message
    assert error.args == (message,)
    assert error.__cause__ is None
    assert error.__context__ is None


def test_known_failure_closes_after_later_same_lane_success():
    client = _Client()
    controller = SecurityAuditGapController(client)
    failure = SecurityAuditUnavailable()
    result = _stored()
    sink = controller.authentication_sink(_Sink((failure, result)))

    with pytest.raises(SecurityAuditUnavailable) as raised:
        sink.append("CREDENTIAL_MISSING")
    returned = sink.append("CREDENTIAL_MISSING")

    assert raised.value is failure
    assert returned is result
    assert controller.state is SecurityAuditGapState.CLEAR
    assert len(client.calls) == 1
    snapshot = client.calls[0]
    assert snapshot.interval_start == NOW
    assert snapshot.event_count == 1
    assert snapshot.count_unknown is False
    assert snapshot.authentication == gap._LaneProgress(1, 2)
    assert snapshot.request_router is None


class _UnavailableSubclass(SecurityAuditUnavailable):
    pass


@pytest.mark.parametrize(
    ("failure", "event_count", "count_unknown"),
    (
        (SecurityAuditUnavailable(), 1, False),
        (SecurityAuditRefused(), 1, False),
        (SecurityAuditOutcomeUnknown(uuid4(), None), 0, True),
        (LookupError("foreign"), 0, True),
        (_UnavailableSubclass(), 0, True),
    ),
)
def test_failure_count_classification_is_exact(
    failure,
    event_count,
    count_unknown,
):
    client = _Client()
    controller = SecurityAuditGapController(client)
    sink = controller.authentication_sink(_Sink((failure, _stored())))

    with pytest.raises(type(failure)) as raised:
        sink.append("CREDENTIAL_MISSING")
    sink.append("CREDENTIAL_MISSING")

    assert raised.value is failure
    assert client.calls[0].event_count == event_count
    assert client.calls[0].count_unknown is count_unknown


def test_base_exception_is_not_caught_or_recorded():
    class ForcedTermination(BaseException):
        pass

    client = _Client()
    controller = SecurityAuditGapController(client)
    failure = ForcedTermination()
    sink = controller.authentication_sink(_Sink((failure,)))

    with pytest.raises(ForcedTermination) as raised:
        sink.append("CREDENTIAL_MISSING")

    assert raised.value is failure
    assert controller.state is SecurityAuditGapState.CLEAR
    assert client.calls == []


def test_cross_lane_success_cannot_close_authentication_failure():
    client = _Client()
    controller = SecurityAuditGapController(client)
    authentication = controller.authentication_sink(
        _Sink((SecurityAuditUnavailable(), _stored()))
    )
    request_router = controller.request_router_sink(_Sink((_stored(),)))

    with pytest.raises(SecurityAuditUnavailable):
        authentication.append("CREDENTIAL_MISSING")
    request_router.append("BINDER_REFUSED")

    assert client.calls == []
    assert controller.state is SecurityAuditGapState.OPEN
    authentication.append("CREDENTIAL_MISSING")
    assert len(client.calls) == 1


class _OutOfOrderSink:
    def __init__(self):
        self.first_started = Event()
        self.release_first = Event()
        self.calls = 0
        self.failure = SecurityAuditUnavailable()

    def append(self, _reason):
        self.calls += 1
        if self.calls == 1:
            self.first_started.set()
            assert self.release_first.wait(5)
            raise self.failure
        return _stored(NOW + timedelta(seconds=10 + self.calls))


def test_processed_success_before_older_failure_is_not_recovery():
    client = _Client()
    controller = SecurityAuditGapController(client)
    inner = _OutOfOrderSink()
    sink = controller.authentication_sink(inner)
    failures = []

    def fail_first():
        try:
            sink.append("CREDENTIAL_MISSING")
        except Exception as error:  # test thread observation only
            failures.append(error)

    thread = Thread(target=fail_first)
    thread.start()
    assert inner.first_started.wait(5)
    sink.append("CREDENTIAL_MISSING")
    inner.release_first.set()
    thread.join(5)

    assert failures == [inner.failure]
    assert controller.state is SecurityAuditGapState.OPEN
    assert client.calls == []
    sink.append("CREDENTIAL_MISSING")
    assert client.calls[0].interval_start == NOW
    assert client.calls[0].authentication == gap._LaneProgress(1, 3)


def test_success_anchor_advances_only_future_ticket_lower_bounds():
    client = _Client()
    controller = SecurityAuditGapController(client)
    advanced = NOW + timedelta(minutes=5)
    sink = controller.authentication_sink(
        _Sink((_overflow(advanced), SecurityAuditUnavailable(), _stored()))
    )

    sink.append("CREDENTIAL_MISSING")
    with pytest.raises(SecurityAuditUnavailable):
        sink.append("CREDENTIAL_MISSING")
    sink.append("CREDENTIAL_MISSING")

    assert client.calls[0].interval_start == advanced


def test_precommit_failure_restores_and_later_success_retries_once():
    client = _Client(
        outcomes=(
            SecurityAuditGapUnavailable(),
            NOW + timedelta(seconds=40),
        )
    )
    controller = SecurityAuditGapController(client)
    sink = controller.authentication_sink(
        _Sink((SecurityAuditUnavailable(), _stored(), _stored()))
    )

    with pytest.raises(SecurityAuditUnavailable):
        sink.append("CREDENTIAL_MISSING")
    with pytest.raises(SecurityAuditGapUnavailable) as raised:
        sink.append("CREDENTIAL_MISSING")

    assert type(raised.value) is SecurityAuditGapUnavailable
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert controller.state is SecurityAuditGapState.OPEN
    sink.append("CREDENTIAL_MISSING")
    assert len(client.calls) == 2
    assert controller.state is SecurityAuditGapState.CLEAR


def test_commit_ambiguity_is_terminal_but_inner_delivery_continues():
    client = _Client(outcomes=(SecurityAuditGapOutcomeUnknown(),))
    controller = SecurityAuditGapController(client)
    inner = _Sink((SecurityAuditUnavailable(), _stored(), _stored()))
    sink = controller.authentication_sink(inner)

    with pytest.raises(SecurityAuditUnavailable):
        sink.append("CREDENTIAL_MISSING")
    with pytest.raises(SecurityAuditGapOutcomeUnknown) as first:
        sink.append("CREDENTIAL_MISSING")
    with pytest.raises(SecurityAuditGapOutcomeUnknown) as second:
        sink.append("CREDENTIAL_MISSING")

    assert type(first.value) is SecurityAuditGapOutcomeUnknown
    assert first.value.__cause__ is None
    assert first.value.__context__ is None
    assert type(second.value) is SecurityAuditGapOutcomeUnknown
    assert controller.state is SecurityAuditGapState.OUTCOME_UNKNOWN
    assert len(inner.calls) == 3
    assert len(client.calls) == 1


def test_inner_failure_remains_primary_after_terminal_ambiguity():
    client = _Client(outcomes=(SecurityAuditGapOutcomeUnknown(),))
    controller = SecurityAuditGapController(client)
    later_failure = SecurityAuditRefused()
    sink = controller.authentication_sink(
        _Sink((SecurityAuditUnavailable(), _stored(), later_failure))
    )

    with pytest.raises(SecurityAuditUnavailable):
        sink.append("CREDENTIAL_MISSING")
    with pytest.raises(SecurityAuditGapOutcomeUnknown):
        sink.append("CREDENTIAL_MISSING")
    with pytest.raises(SecurityAuditRefused) as raised:
        sink.append("CREDENTIAL_MISSING")

    assert raised.value is later_failure
    assert len(client.calls) == 1


class _BlockingClient(_Client):
    def __init__(self):
        super().__init__()
        self.close_started = Event()
        self.release_close = Event()

    def append(self, snapshot):
        self.calls.append(snapshot)
        if len(self.calls) == 1:
            self.close_started.set()
            assert self.release_close.wait(5)
        return NOW + timedelta(seconds=30 + len(self.calls))


def test_one_closing_snapshot_and_one_concurrent_accumulator():
    client = _BlockingClient()
    controller = SecurityAuditGapController(client)
    inner = _Sink(
        (
            SecurityAuditUnavailable(),
            _stored(),
            SecurityAuditUnavailable(),
            _stored(),
        )
    )
    sink = controller.authentication_sink(inner)
    results = []

    with pytest.raises(SecurityAuditUnavailable):
        sink.append("CREDENTIAL_MISSING")

    thread = Thread(
        target=lambda: results.append(sink.append("CREDENTIAL_MISSING"))
    )
    thread.start()
    assert client.close_started.wait(5)
    with pytest.raises(SecurityAuditUnavailable):
        sink.append("CREDENTIAL_MISSING")
    assert controller.state is SecurityAuditGapState.CLOSING
    assert len(client.calls) == 1
    client.release_close.set()
    thread.join(5)

    assert len(results) == 1
    assert controller.state is SecurityAuditGapState.OPEN
    sink.append("CREDENTIAL_MISSING")
    assert len(client.calls) == 2
    assert client.calls[1].event_count == 1


def test_simultaneous_two_lane_recovery_claims_one_close():
    barrier = Barrier(2)

    def recovered():
        barrier.wait(timeout=5)
        return _stored()

    client = _Client()
    controller = SecurityAuditGapController(client)
    authentication = controller.authentication_sink(
        _Sink((SecurityAuditUnavailable(), recovered))
    )
    request_router = controller.request_router_sink(
        _Sink((SecurityAuditRefused(), recovered))
    )
    for sink in (authentication, request_router):
        with pytest.raises((SecurityAuditUnavailable, SecurityAuditRefused)):
            sink.append("KNOWN_FAILURE")
    results = []
    errors = []

    def succeed(sink):
        try:
            results.append(sink.append("RECOVERY"))
        except Exception as error:  # test thread observation only
            errors.append(error)

    threads = [
        Thread(target=succeed, args=(authentication,)),
        Thread(target=succeed, args=(request_router,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)

    assert errors == []
    assert len(results) == 2
    assert len(client.calls) == 1
    assert client.calls[0].event_count == 2
    assert controller.state is SecurityAuditGapState.CLEAR


@pytest.mark.parametrize(
    ("recovery", "expected"),
    ((6, None), (12, 12)),
)
def test_precommit_merge_revalidates_concurrent_recovery(recovery, expected):
    closing = gap._GapSnapshot(
        NOW,
        1,
        gap._LaneProgress(10, 11),
        None,
    )
    concurrent = gap._Accumulator(
        NOW + timedelta(seconds=1),
        1,
        gap._LaneProgress(5, recovery),
        None,
    )

    merged = gap._merge(closing, concurrent)

    assert merged.authentication == gap._LaneProgress(10, expected)
    assert merged.exact_count == 2


def test_signed_bigint_helpers_saturate_without_unbounded_growth():
    maximum = gap.SIGNED_BIGINT_MAX

    assert gap._bounded_sum(maximum - 1, 1) == maximum
    assert gap._bounded_sum(maximum, 1) is None
    assert gap._bounded_sum(None, 1) is None
    assert gap._next_sequence(maximum - 1) == maximum
    assert gap._next_sequence(maximum) is None


def test_lane_sequence_exhaustion_stops_before_inner_sink(monkeypatch):
    monkeypatch.setattr(gap, "SIGNED_BIGINT_MAX", 1)
    controller = SecurityAuditGapController(_Client())
    inner = _Sink((_stored(), _stored()))
    sink = controller.authentication_sink(inner)

    sink.append("CREDENTIAL_MISSING")
    with pytest.raises(SecurityAuditGapOutcomeUnknown):
        sink.append("CREDENTIAL_MISSING")

    assert len(inner.calls) == 1
    assert controller.state is SecurityAuditGapState.OUTCOME_UNKNOWN


def test_combined_lane_count_saturation_closes_as_unknown(monkeypatch):
    monkeypatch.setattr(gap, "SIGNED_BIGINT_MAX", 3)
    client = _Client()
    controller = SecurityAuditGapController(client)
    authentication = controller.authentication_sink(
        _Sink((SecurityAuditUnavailable(), SecurityAuditUnavailable(), _stored()))
    )
    request_router = controller.request_router_sink(
        _Sink((SecurityAuditRefused(), SecurityAuditRefused(), _stored()))
    )

    for sink in (authentication, authentication, request_router, request_router):
        with pytest.raises((SecurityAuditUnavailable, SecurityAuditRefused)):
            sink.append("KNOWN_FAILURE")
    authentication.append("RECOVERY")
    request_router.append("RECOVERY")

    assert len(client.calls) == 1
    assert client.calls[0].event_count == 0
    assert client.calls[0].count_unknown is True


def test_lane_binding_is_fixed_and_non_repeatable():
    controller = SecurityAuditGapController(_Client())
    sink = _Sink((_stored(),))

    controller.authentication_sink(sink)
    controller.request_router_sink(sink)

    with pytest.raises(ValueError):
        controller.authentication_sink(sink)
    with pytest.raises(ValueError):
        controller.request_router_sink(sink)


def test_fresh_controller_does_not_reconcile_prior_process_state():
    first = SecurityAuditGapController(_Client())
    sink = first.authentication_sink(_Sink((SecurityAuditUnavailable(),)))

    with pytest.raises(SecurityAuditUnavailable):
        sink.append("CREDENTIAL_MISSING")

    second_client = _Client(anchor=NOW + timedelta(hours=1))
    second = SecurityAuditGapController(second_client)
    second.authentication_sink(_Sink((_stored(),))).append(
        "CREDENTIAL_MISSING"
    )
    assert first.state is SecurityAuditGapState.OPEN
    assert second.state is SecurityAuditGapState.CLEAR
    assert second_client.calls == []


class _Cursor:
    def __init__(self, rows):
        self._rows = iter(rows)

    def fetchone(self):
        return next(self._rows, None)


class _Info:
    transaction_status = TransactionStatus.IDLE


class _DatabaseConnection:
    def __init__(
        self,
        responses,
        *,
        execute_errors=None,
        commit_error=None,
        close_error=None,
    ):
        self.closed = False
        self.autocommit = False
        self.isolation_level = None
        self.info = _Info()
        self.responses = responses
        self.execute_errors = execute_errors or {}
        self.commit_error = commit_error
        self.close_error = close_error
        self.events = []

    def execute(self, query, parameters=None):
        self.events.append(("execute", query, parameters))
        error = self.execute_errors.get(query)
        if error is not None:
            raise error
        return _Cursor(self.responses.get(query, ()))

    def rollback(self):
        self.events.append(("rollback",))

    def commit(self):
        self.events.append(("commit",))
        if self.commit_error is not None:
            raise self.commit_error

    def close(self):
        self.events.append(("close",))
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class _ConnectionFactory:
    def __init__(self, connections):
        self.connections = list(connections)
        self.calls = []

    def __call__(self, conninfo, **kwargs):
        self.calls.append((conninfo, kwargs))
        return self.connections.pop(0)


def _initial_connection(
    user=gap.AUDIT_CONTROL_LOGIN,
    synchronous_commit="on",
):
    return _DatabaseConnection(
        {
            gap._INITIALIZE: (
                (user, synchronous_commit, NOW),
            )
        }
    )


def _closing_connection(*, commit_error=None, close_error=None, execute_errors=None):
    end = NOW + timedelta(seconds=20)
    observed = end + timedelta(seconds=1)
    return _DatabaseConnection(
        {
            gap._AUTHORITY: ((gap.AUDIT_CONTROL_LOGIN, "on"),),
            gap._CLOCK: ((end,),),
            gap._APPEND: (
                (uuid4(), observed, observed + timedelta(days=30)),
            ),
        },
        commit_error=commit_error,
        close_error=close_error,
        execute_errors=execute_errors,
    )


def _client_controller(factory, conninfo="dbname=audit"):
    return SecurityAuditGapController(
        SecurityAuditGapClient(conninfo, connection_factory=factory)
    )


def test_client_pins_connection_options_over_conflicting_dsn():
    connection = _initial_connection()
    factory = _ConnectionFactory((connection,))
    conninfo = (
        "dbname=audit connect_timeout=999 "
        "options='-c statement_timeout=999999 -c synchronous_commit=off'"
    )

    controller = _client_controller(factory, conninfo)
    observed_conninfo, observed_kwargs = factory.calls[0]
    conninfo_kwargs = dict(observed_kwargs)
    assert conninfo_kwargs.pop("autocommit") is False
    merged = conninfo_to_dict(
        make_conninfo(observed_conninfo, **conninfo_kwargs)
    )

    assert controller.state is SecurityAuditGapState.CLEAR
    assert merged == {
        "connect_timeout": "5",
        "dbname": "audit",
        "options": gap.GAP_CONNECTION_OPTIONS,
    }
    assert connection.isolation_level is IsolationLevel.READ_COMMITTED
    assert connection.events == [
        ("execute", gap._INITIALIZE_TRANSACTION, None),
        ("execute", gap._INITIALIZE, None),
        ("rollback",),
        ("close",),
    ]


@pytest.mark.parametrize(
    ("user", "setting"),
    (
        ("ofarm_security_audit_reader_login", "on"),
        (gap.AUDIT_CONTROL_LOGIN, "off"),
    ),
)
def test_client_initialization_refuses_wrong_authority_or_durability(
    user,
    setting,
):
    connection = _initial_connection(user, setting)

    with pytest.raises(SecurityAuditGapUnavailable) as raised:
        _client_controller(_ConnectionFactory((connection,)))

    assert type(raised.value) is SecurityAuditGapUnavailable
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert not any(event[0] == "commit" for event in connection.events)


def test_client_calls_exact_gap_function_and_commits_once():
    initial = _initial_connection()
    closing = _closing_connection()
    factory = _ConnectionFactory((initial, closing))
    controller = _client_controller(factory)
    sink = controller.authentication_sink(
        _Sink((SecurityAuditUnavailable(), _stored()))
    )

    with pytest.raises(SecurityAuditUnavailable):
        sink.append("CREDENTIAL_MISSING")
    result = sink.append("CREDENTIAL_MISSING")

    assert type(result) is StoredAuditAppend
    assert len(factory.calls) == 2
    assert factory.calls[1][1] == {
        "autocommit": False,
        "connect_timeout": 5,
        "options": gap.GAP_CONNECTION_OPTIONS,
    }
    append_event = next(
        event
        for event in closing.events
        if event[0] == "execute" and event[1] == gap._APPEND
    )
    assert append_event[2] == (
        NOW,
        NOW + timedelta(seconds=20),
        1,
        False,
    )
    assert closing.events[-2:] == [("commit",), ("close",)]


def test_client_precommit_failure_rolls_back_and_restores():
    dependency = RuntimeError("dependency detail")
    initial = _initial_connection()
    closing = _closing_connection(execute_errors={gap._APPEND: dependency})
    controller = _client_controller(_ConnectionFactory((initial, closing)))
    sink = controller.authentication_sink(
        _Sink((SecurityAuditUnavailable(), _stored()))
    )

    with pytest.raises(SecurityAuditUnavailable):
        sink.append("CREDENTIAL_MISSING")
    with pytest.raises(SecurityAuditGapUnavailable) as raised:
        sink.append("CREDENTIAL_MISSING")

    assert type(raised.value) is SecurityAuditGapUnavailable
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert controller.state is SecurityAuditGapState.OPEN
    assert ("rollback",) in closing.events
    assert ("commit",) not in closing.events


@pytest.mark.parametrize(
    "interval_end",
    (NOW, NOW - timedelta(microseconds=1)),
)
def test_client_refuses_non_increasing_end_before_gap_call(interval_end):
    initial = _initial_connection()
    closing = _DatabaseConnection(
        {
            gap._AUTHORITY: ((gap.AUDIT_CONTROL_LOGIN, "on"),),
            gap._CLOCK: ((interval_end,),),
        }
    )
    controller = _client_controller(_ConnectionFactory((initial, closing)))
    sink = controller.authentication_sink(
        _Sink((SecurityAuditUnavailable(), _stored()))
    )

    with pytest.raises(SecurityAuditUnavailable):
        sink.append("CREDENTIAL_MISSING")
    with pytest.raises(SecurityAuditGapUnavailable):
        sink.append("CREDENTIAL_MISSING")

    assert not any(
        event[0] == "execute" and event[1] == gap._APPEND
        for event in closing.events
    )
    assert controller.state is SecurityAuditGapState.OPEN


def test_client_commit_exception_is_terminal_and_never_rolls_back():
    initial = _initial_connection()
    closing = _closing_connection(commit_error=RuntimeError("ack lost"))
    controller = _client_controller(_ConnectionFactory((initial, closing)))
    sink = controller.authentication_sink(
        _Sink((SecurityAuditUnavailable(), _stored()))
    )

    with pytest.raises(SecurityAuditUnavailable):
        sink.append("CREDENTIAL_MISSING")
    with pytest.raises(SecurityAuditGapOutcomeUnknown) as raised:
        sink.append("CREDENTIAL_MISSING")

    assert type(raised.value) is SecurityAuditGapOutcomeUnknown
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert controller.state is SecurityAuditGapState.OUTCOME_UNKNOWN
    assert ("commit",) in closing.events
    assert ("rollback",) not in closing.events


def test_client_post_acknowledgement_close_failure_cannot_revoke_success():
    initial = _initial_connection()
    closing = _closing_connection(close_error=RuntimeError("close failed"))
    controller = _client_controller(_ConnectionFactory((initial, closing)))
    result = _stored()
    sink = controller.authentication_sink(
        _Sink((SecurityAuditUnavailable(), result))
    )

    with pytest.raises(SecurityAuditUnavailable):
        sink.append("CREDENTIAL_MISSING")

    assert sink.append("CREDENTIAL_MISSING") is result
    assert controller.state is SecurityAuditGapState.CLEAR
    assert closing.events[-2:] == [("commit",), ("close",)]
