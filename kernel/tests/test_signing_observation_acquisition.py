"""B1: actual SIGINT at acquisition/return cannot strand retained native I/O."""
from __future__ import annotations

import inspect
import os
import signal
import socket
import sys
import time

import pytest
from psycopg.waiting import Wait

from kernel import postgres_wait as mechanical
from kernel import signing_authority as authority_module
from kernel import signing_authority_io as transport
from kernel.tests._signing_observation_support import reader
from kernel.tests.test_postgresql_tenant_migration import (
    authority, capability_key, tenant_target,  # noqa: F401 - real fixtures
)
from kernel.tests.test_signing_observation_database import (
    _assert_native_handles_disposed, _retain_native_handles,
    observation,  # noqa: F401 - signed real-role observation fixture
)


def _source_line(function, marker):
    lines, first = inspect.getsourcelines(function)
    matches = [first + index for index, line in enumerate(lines) if marker in line]
    assert len(matches) == 1, "signal boundary must identify exactly one source line"
    return matches[0]


def _interrupt(function, call, *, line=None, event="line"):
    assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
    previous = sys.gettrace()
    delivered = []
    def trace(frame, observed, _arg):
        if frame.f_code is function.__code__ and observed == event:
            if line is None or frame.f_lineno == line:
                sys.settrace(previous)
                if event == "return":
                    assert _arg is not None, "signal must follow successful helper completion"
                delivered.append(True)
                signal.raise_signal(signal.SIGINT)
        return trace
    sys.settrace(trace)
    try:
        with pytest.raises(KeyboardInterrupt) as raised:
            call()
    finally:
        sys.settrace(previous)
    assert delivered == [True]
    assert raised.value.__traceback__ is not None
    return raised.value


def _assert_closed(descriptor):
    with pytest.raises(OSError):
        os.fstat(descriptor)


@pytest.mark.parametrize("stage", (
    "partial", "wrapper", "return-line", "return-event", "reader", "cursor",
))
def test_sigint_across_native_connection_acquisition_and_handoff(
    observation, monkeypatch, stage,
):
    dsn, expected, path = observation
    bounded = reader(dsn, path)
    handles = _retain_native_handles(monkeypatch)
    cursors = []
    actual_cursor = transport._BoundedConnection.cursor
    def capture_cursor(connection):
        cursor = actual_cursor(connection)
        cursors.append(cursor)
        return cursor
    monkeypatch.setattr(transport._BoundedConnection, "cursor", capture_cursor)
    function = transport.connect_observation
    markers = {
        "partial": "wait(_connect_existing(owner.pgconn)",
        "wrapper": "connection = owner.connection",
        "return-line": "return connection",
        "reader": "cursor = None",
        "cursor": "cursor.execute(_SIGNING_AUTHORITY_QUERY",
    }
    if stage in ("reader", "cursor"):
        function = authority_module.SigningAuthorityReader.current
    line = None if stage == "return-event" else _source_line(function, markers[stage])
    try:
        retained = _interrupt(
            function, lambda: bounded.current(expected.kid), line=line,
            event="return" if stage == "return-event" else "line",
        )
        assert retained.__traceback__ is not None and len(handles) == 1
        _assert_native_handles_disposed(handles)
        if stage == "cursor":
            assert len(cursors) == 1 and cursors[0].closed
        else:
            assert not cursors
    finally:
        # Probe containment follows assertions; it cannot make a leak test pass.
        for cursor in cursors:
            cursor.close()
        for handle, _descriptor in handles:
            handle.finish()


def test_sigint_immediately_after_receipt_open_closes_retained_descriptor(tmp_path, monkeypatch):
    path = tmp_path / "receipt"
    path.write_bytes(b"fixture")
    descriptors = []
    native_open = os.open
    def capture_open(*args):
        descriptor = native_open(*args)
        descriptors.append(descriptor)
        return descriptor
    monkeypatch.setattr(transport.os, "open", capture_open)
    line = _source_line(transport.read_signing_receipt, "descriptor = os.open") + 1
    try:
        retained = _interrupt(
            transport.read_signing_receipt,
            lambda: transport.read_signing_receipt(path, deadline=time.monotonic() + 1),
            line=line,
        )
        assert retained.__traceback__ is not None and len(descriptors) == 1
        _assert_closed(descriptors[0])
    finally:
        for descriptor in descriptors:
            try:
                os.close(descriptor)
            except OSError:
                pass


def test_sigint_immediately_after_native_selector_acquisition_closes_it(monkeypatch):
    selectors = []
    native_selector = mechanical.selectors.DefaultSelector
    def capture_selector():
        selector = native_selector()
        selectors.append((selector, selector.fileno()))
        return selector
    monkeypatch.setattr(mechanical.selectors, "DefaultSelector", capture_selector)
    left, right = socket.socketpair()
    def operation():
        yield Wait.R
    generator = operation()
    line = _source_line(mechanical.wait, "selector = selectors.DefaultSelector()") + 1
    try:
        retained = _interrupt(
            mechanical.wait,
            lambda: mechanical.wait(generator, left.fileno, time.monotonic() + 1),
            line=line,
        )
        assert retained.__traceback__ is not None and len(selectors) == 1
        selector, descriptor = selectors[0]
        _assert_closed(descriptor)
        assert selector.get_map() is None
        with pytest.raises(StopIteration):
            next(generator)
    finally:
        generator.close()
        for selector, _descriptor in selectors:
            selector.close()
        left.close()
        right.close()


@pytest.mark.parametrize("stage", ("connect", "cursor", "selector", "receipt"))
def test_process_control_before_acquisition_handles_empty_owner_slots(
    observation, monkeypatch, stage,
):
    dsn, expected, path = observation
    bounded = reader(dsn, path)
    handles = _retain_native_handles(monkeypatch)
    control = KeyboardInterrupt()
    def refuse(*_args, **_kwargs):
        raise control
    if stage == "connect":
        monkeypatch.setattr(transport.pq.PGconn, "connect_start", refuse)
    elif stage == "cursor":
        monkeypatch.setattr(transport._BoundedConnection, "cursor", refuse)
    elif stage == "selector":
        monkeypatch.setattr(mechanical.selectors, "DefaultSelector", refuse)
    else:
        monkeypatch.setattr(transport.os, "open", refuse)
    try:
        with pytest.raises(KeyboardInterrupt) as retained:
            bounded.current(expected.kid)
        assert retained.value is control and control.__traceback__ is not None
        if stage == "connect":
            assert not handles
        else:
            _assert_native_handles_disposed(handles)
    finally:
        for handle, _descriptor in handles:
            handle.finish()
