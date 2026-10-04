"""S1-02/05/07 mechanical waiting and explicit partial-handle ownership."""
from __future__ import annotations

import os
import socket
import threading
import time
from types import SimpleNamespace

import psycopg
import pytest
from psycopg import pq
from psycopg.waiting import Wait

from kernel import postgres_wait as mechanical
from kernel import signing_authority_io as transport
BASE = "dbname=ofarm user=ofarm_app password=fixture sslmode=disable gssencmode=disable"


class Selector:
    def __init__(self, replies=(), failure=None, close_failure=None):
        self.replies = iter(replies)
        self.failure = failure
        self.close_failure = close_failure
        self.events = []
        self.closed = False

    def register(self, fd, mask):
        self.events.append(("register", fd, mask))

    def unregister(self, fd):
        self.events.append(("unregister", fd))

    def modify(self, fd, mask):
        self.events.append(("modify", fd, mask))

    def select(self, timeout):
        assert 0 <= timeout <= 0.05
        if self.failure:
            raise self.failure
        return next(self.replies)

    def close(self):
        self.closed = True
        if self.close_failure:
            raise self.close_failure


def test_wait_refreshes_changed_descriptors_empty_polls_and_combined_readiness(monkeypatch):
    selector = Selector(([], [(None, 3)], [(None, 1)]))
    monkeypatch.setattr(mechanical.selectors, "DefaultSelector", lambda: selector)
    descriptor = [11]
    finished = []
    def operation():
        try:
            assert (yield Wait.RW) == 0
            descriptor[0] = 12
            assert (yield Wait.RW) == 3
            assert (yield Wait.R) == 1
            return "complete"
        finally:
            finished.append(True)
    retained = operation()
    assert mechanical.wait(retained, lambda: descriptor[0], time.monotonic() + 1) == "complete"
    assert selector.closed and finished == [True]
    assert ("unregister", 11) in selector.events
    assert ("register", 12, 3) in selector.events
    with pytest.raises(StopIteration):
        next(retained)


@pytest.mark.parametrize("failure", (OSError("selector failure"), KeyboardInterrupt(), SystemExit()))
def test_selector_error_retained_exception_still_closes_generator(monkeypatch, failure):
    selector = Selector(failure=failure)
    monkeypatch.setattr(mechanical.selectors, "DefaultSelector", lambda: selector)
    finished = []
    def operation():
        try:
            yield Wait.R
        finally:
            finished.append(True)
    retained = operation()
    with pytest.raises(type(failure)) as raised:
        mechanical.wait(retained, lambda: 11, time.monotonic() + 1)
    assert raised.value is failure and selector.closed and finished == [True]


def test_generator_cleanup_failure_cannot_skip_selector_cleanup(monkeypatch):
    selector = Selector(failure=OSError("select refused"))
    monkeypatch.setattr(mechanical.selectors, "DefaultSelector", lambda: selector)
    def operation():
        try:
            yield Wait.R
        finally:
            raise RuntimeError("generator disposal refused")
    retained = operation()
    with pytest.raises(RuntimeError) as raised:
        mechanical.wait(retained, lambda: 11, time.monotonic() + 1)
    assert selector.closed
    assert raised.value.__context__ is not None


def test_completion_then_cancellation_is_not_published_and_generator_is_closed(monkeypatch):
    stop = threading.Event()
    selector = Selector(([(None, 1)],))
    monkeypatch.setattr(mechanical.selectors, "DefaultSelector", lambda: selector)
    finished = []
    def operation():
        try:
            yield Wait.R
            stop.set()
            return "late completion"
        finally:
            finished.append(True)
    retained = operation()
    with pytest.raises(mechanical.PostgresWaitStopped):
        mechanical.wait(retained, lambda: 11, time.monotonic() + 1, stop)
    assert selector.closed and finished == [True]


def test_real_selector_cancellation_is_polled_without_socket_readiness():
    left, right = socket.socketpair()
    stop = threading.Event()
    closed = []
    def operation():
        try:
            while True:
                yield Wait.R
        finally:
            closed.append(True)
    retained = operation()
    timer = threading.Timer(0.02, stop.set)
    timer.start()
    started = time.monotonic()
    try:
        with pytest.raises(mechanical.PostgresWaitStopped):
            mechanical.wait(retained, left.fileno, started + 1, stop)
        assert time.monotonic() - started < 0.15
        assert closed == [True]
    finally:
        timer.join(1)
        left.close()
        right.close()


@pytest.mark.parametrize("value", (True, False, float("inf"), float("nan"), "later"))
def test_invalid_deadline_never_disables_the_mechanical_limit(value):
    with pytest.raises(mechanical.PostgresWaitStopped):
        mechanical.checkpoint(value, None)


class PartialHandle:
    def __init__(self, states, *, stop=None, finish_failure=False):
        self.states = iter(states)
        self.client, self.peer = socket.socketpair()
        self.socket = self.client.fileno()
        self.original_fd = self.socket
        self.status = pq.ConnStatus.STARTED
        self.nonblocking = 1
        self.finished = 0
        self.stop = stop
        self.finish_failure = finish_failure

    def connect_poll(self):
        state = next(self.states)
        if isinstance(state, BaseException):
            if isinstance(state, psycopg.OperationalError):
                raise psycopg.OperationalError(*state.args, pgconn=self)
            state.pgconn = self
            raise state
        if self.stop:
            self.stop.set()
        if state is pq.PollingStatus.OK:
            self.status = pq.ConnStatus.OK
        return state

    def finish(self):
        self.finished += 1
        self.client.close()
        self.peer.close()
        self.status = pq.ConnStatus.BAD
        self.socket = -1
        if self.finish_failure:
            raise OSError("native finish fault after disposal")


def _install_partial(monkeypatch, handle):
    frozen = transport.prepare_signing_conninfo(f"host=127.0.0.1 port=5432 {BASE}")
    # Only replace the handle constructor after pure production preflight.
    monkeypatch.setattr(transport.pq, "PGconn", SimpleNamespace(connect_start=lambda _: handle))
    return frozen


def _assert_partial_disposed(handle):
    assert handle.finished == 1 and handle.status is pq.ConnStatus.BAD
    with pytest.raises(OSError):
        os.fstat(handle.original_fd)


@pytest.mark.parametrize("failure", (
    psycopg.OperationalError("fixture DSN password=must-not-escape"),
    TimeoutError("poll timeout"), KeyboardInterrupt(), SystemExit(),
))
def test_poll_failure_retains_pgconn_but_handle_already_finished(monkeypatch, failure):
    handle = PartialHandle([failure])
    frozen = _install_partial(monkeypatch, handle)
    with pytest.raises(type(failure)) as retained:
        transport.connect_observation(frozen, time.monotonic() + 1, None)
    assert type(retained.value) is type(failure) and retained.value.pgconn is handle
    assert retained.value.__traceback__ is not None
    _assert_partial_disposed(handle)


@pytest.mark.parametrize("state", (pq.PollingStatus.READING, pq.PollingStatus.OK))
def test_cancel_during_first_poll_or_success_disposes_owned_completion(monkeypatch, state):
    stop = threading.Event()
    handle = PartialHandle([state], stop=stop)
    frozen = _install_partial(monkeypatch, handle)
    with pytest.raises(mechanical.PostgresWaitStopped):
        transport.connect_observation(frozen, time.monotonic() + 1, stop)
    _assert_partial_disposed(handle)


def test_connection_construction_failure_retains_no_live_partial_handle(monkeypatch):
    handle = PartialHandle([pq.PollingStatus.OK])
    frozen = _install_partial(monkeypatch, handle)
    failure = RuntimeError("constructor failed")
    def fail(_handle):
        raise failure
    monkeypatch.setattr(transport, "_BoundedConnection", fail)
    with pytest.raises(RuntimeError) as retained:
        transport.connect_observation(frozen, time.monotonic() + 1, None)
    assert retained.value is failure
    _assert_partial_disposed(handle)


def test_nested_wait_and_handle_cleanup_failures_still_dispose_all(monkeypatch):
    handle = PartialHandle([pq.PollingStatus.READING], finish_failure=True)
    frozen = _install_partial(monkeypatch, handle)
    selector = Selector(failure=OSError("wait fault"), close_failure=RuntimeError("selector close fault"))
    monkeypatch.setattr(mechanical.selectors, "DefaultSelector", lambda: selector)
    with pytest.raises(OSError) as retained:
        transport.connect_observation(frozen, time.monotonic() + 1, None)
    assert selector.closed and retained.value.__context__ is not None
    _assert_partial_disposed(handle)


def test_pinned_binary_initial_bad_handle_is_finished_by_the_production_owner(monkeypatch):
    assert psycopg.__version__ == "3.3.4" and pq.__impl__ == "binary"
    frozen = transport.prepare_signing_conninfo(f"host=127.0.0.1 port=5432 {BASE}")
    native_start = pq.PGconn.connect_start
    retained = []
    def initial_bad(_conninfo):
        handle = native_start(b"invalid_conninfo_option=fixture")
        assert handle.status == pq.ConnStatus.BAD
        assert handle.error_message
        retained.append(handle)
        return handle
    monkeypatch.setattr(transport.pq, "PGconn", SimpleNamespace(connect_start=initial_bad))
    errors = []
    for _ in range(5):
        with pytest.raises(psycopg.OperationalError) as raised:
            transport.connect_observation(frozen, time.monotonic() + 1, None)
        errors.append(raised.value)
    # The pinned binding exposes a NULL pointer diagnostic only after finish.
    assert all(b"connection pointer is NULL" in handle.error_message for handle in retained)
    assert all(error.__traceback__ is not None for error in errors)


@pytest.mark.parametrize("control", (KeyboardInterrupt(), SystemExit()))
def test_process_control_survives_nested_selector_cleanup_failure(monkeypatch, control):
    selector = Selector(close_failure=OSError("selector disposal failed"))
    monkeypatch.setattr(mechanical.selectors, "DefaultSelector", lambda: selector)
    def operation():
        raise control
        yield Wait.R
    retained = operation()
    with pytest.raises(type(control)) as raised:
        mechanical.wait(retained, lambda: 11, time.monotonic() + 1)
    assert raised.value is control and selector.closed
