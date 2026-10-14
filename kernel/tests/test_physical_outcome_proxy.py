"""Real socket/TLS fixture controls; the upstream is not database authority."""
from __future__ import annotations

import inspect
import socket
import ssl
import struct
import sys
from threading import Event, Thread, current_thread

import pytest

from kernel.tests._physical_outcome_proxy import PhysicalWireProxy
from kernel.tests._signing_observation_proxy import _exact, _startup, tls_context


STARTUP = struct.pack("!II", 8, 196608)
SSL_REQUEST = struct.pack("!II", 8, 80877103)


def _query(text=b"SELECT 1"):
    return b"Q" + struct.pack("!I", len(text) + 5) + text + b"\0"


class _Wire:
    """Own a local packet echo peer and the actual proxy; no database involved."""

    def __init__(self, directory, encrypted=True, on_commit=None):
        tls, certificate = tls_context(directory)
        self.encrypted, self.certificate = encrypted, certificate
        self.stop, self.started = Event(), Event()
        self.sockets, self.clients, self.errors = [], [], []
        self.closed = False
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()
        self.listener.settimeout(.1)
        self.peer = Thread(target=self._serve, name="physical-proxy-test-peer")
        self.proxy = PhysicalWireProxy(
            f"host=127.0.0.1 port={self.listener.getsockname()[1]} dbname=fixture user=fixture",
            tls=tls if encrypted else None, certificate=certificate, on_commit=on_commit,
        )
        self.peer.start()
        self.proxy.__enter__()

    def _serve(self):
        try:
            while not self.stop.is_set():
                try:
                    connection, _ = self.listener.accept()
                    break
                except TimeoutError:
                    continue
            else:
                return
            self.sockets.append(connection)
            connection.settimeout(3)
            assert _startup(connection) == STARTUP
            self.started.set()
            while not self.stop.is_set():
                header = _exact(connection, 5)
                packet = header + _exact(connection, struct.unpack("!I", header[1:])[0] - 4)
                if packet == _query(b"COMMIT"):
                    packet = b"C" + struct.pack("!I", 11) + b"COMMIT\0"
                connection.sendall(packet)
        except EOFError:
            pass
        except OSError as failure:
            if not self.stop.is_set():
                self.errors.append(failure)
        except BaseException as failure:
            self.errors.append(failure)
        finally:
            for connection in self.sockets:
                connection.close()

    def connect(self, startup=STARTUP):
        client = socket.create_connection(("127.0.0.1", self.proxy.port), 3)
        self.clients.append(client)
        if self.encrypted:
            client.sendall(SSL_REQUEST)
            if _exact(client, 1) != b"S":
                raise AssertionError("proxy refused the fixture TLS request")
            client = ssl.create_default_context(cafile=str(self.certificate)).wrap_socket(
                client, server_hostname="signing.test",
            )
            self.clients.append(client)
        client.sendall(startup)
        return client

    def finish(self, body=None):
        if self.closed:
            return
        self.closed = True
        try:
            self.proxy.__exit__(type(body) if body else None, body, None)
        finally:
            self.stop.set()
            self.listener.close()
            for connection in [*self.clients, *self.sockets]:
                PhysicalWireProxy._close(connection)
            self.peer.join(2)
            assert not self.peer.is_alive()
            assert not self.errors, self.errors
            assert all(c.fileno() == -1 for c in [*self.clients, *self.sockets, *self.proxy.sockets])


@pytest.fixture
def wires(tmp_path):
    owned = []
    def create(**kwargs):
        wire = _Wire(tmp_path, **kwargs)
        owned.append(wire)
        return wire
    yield create
    for wire in owned:
        wire.finish()


def _leaves(failure):
    if isinstance(failure, BaseExceptionGroup):
        return [leaf for child in failure.exceptions for leaf in _leaves(child)]
    return [failure]


def _closing(wire, errors):
    try:
        wire.finish()
    except BaseException as failure:
        errors.append(failure)


@pytest.mark.parametrize("encrypted", (False, True))
def test_proxy_forwards_real_socket_packets_and_joins_all_owners(wires, encrypted):
    wire = wires(encrypted=encrypted)
    client = wire.connect()
    client.sendall(_query())
    assert _exact(client, len(_query())) == _query()
    wire.finish()
    assert not wire.proxy.failures
    assert not wire.proxy.thread.is_alive()
    assert not any(worker.is_alive() for worker in wire.proxy.workers)


def test_tls_shutdown_cannot_turn_pending_encrypted_read_into_plaintext(wires, monkeypatch):
    wire = wires()
    waiting, allow_read, read_done = Event(), Event(), Event()
    facts, errors = {}, []
    lines, start = inspect.getsourcelines(PhysicalWireProxy._relay)
    recv_line = next(start + i for i, line in enumerate(lines) if "part = source.recv" in line)
    original_connection = wire.proxy._connection
    def trace(frame, event, _arg):
        if event == "line" and frame.f_code is PhysicalWireProxy._relay.__code__:
            if frame.f_lineno == recv_line and isinstance(frame.f_locals["source"], ssl.SSLSocket):
                waiting.set()
                assert allow_read.wait(2)
            if frame.f_lineno == recv_line + 1 and isinstance(frame.f_locals["source"], ssl.SSLSocket):
                facts["read"] = frame.f_locals["part"]
                read_done.set()
        return trace
    def connection(*args):
        sys.settrace(trace)
        try:
            original_connection(*args)
        finally:
            sys.settrace(None)
    native_shutdown = socket.socket.shutdown
    def shutdown(connection, how):
        if (isinstance(connection, ssl.SSLSocket) and connection in wire.proxy.sockets
                and connection.fileno() >= 0 and current_thread().name == "proxy-test-close"):
            facts["tls_preserved"] = connection._sslobj is not None
            allow_read.set()
            assert read_done.wait(2)
        return native_shutdown(connection, how)
    monkeypatch.setattr(wire.proxy, "_connection", connection)
    monkeypatch.setattr(socket.socket, "shutdown", shutdown)
    client = wire.connect()
    assert wire.started.wait(2)
    client.sendall(_query())
    assert waiting.wait(2)
    closing = Thread(target=_closing, args=(wire, errors), name="proxy-test-close")
    try:
        closing.start()
        closing.join(2)
    finally:
        allow_read.set()
        closing.join(2)
    assert not closing.is_alive() and not errors
    assert facts == {"tls_preserved": True, "read": _query()}
    assert not wire.proxy.failures


@pytest.mark.parametrize("encrypted", (False, True))
@pytest.mark.parametrize("body", (None, ValueError("fixture body failure")))
def test_malformed_frame_retains_worker_traceback_and_body_error(wires, encrypted, body):
    wire = wires(encrypted=encrypted)
    client = wire.connect()
    assert wire.started.wait(2)
    client.sendall(b"Q" + struct.pack("!I", 1048576))
    wire.proxy.workers[0].join(2)
    assert not wire.proxy.workers[0].is_alive()
    assert len(wire.proxy.failures) == 1
    original = wire.proxy.failures[0]
    assert type(original) is AssertionError
    with pytest.raises(BaseExceptionGroup) as caught:
        wire.finish(body)
    assert _leaves(caught.value) == ([body] if body else []) + [original]
    frames = []
    trace = original.__traceback__
    while trace:
        frames.append(trace.tb_frame.f_code.co_name)
        trace = trace.tb_next
    assert "_relay" in frames


@pytest.mark.parametrize("failure", (AssertionError("commit callback"), OSError("commit callback"), KeyboardInterrupt("commit callback")))
def test_commit_callback_failure_is_retained_once(wires, failure):
    def callback():
        raise failure
    wire = wires(on_commit=callback)
    client = wire.connect()
    assert wire.started.wait(2)
    client.sendall(_query(b"COMMIT"))
    wire.proxy.workers[0].join(2)
    with pytest.raises(BaseExceptionGroup) as caught:
        wire.finish()
    assert _leaves(caught.value) == [failure]
    assert wire.proxy.failures == [failure]


@pytest.mark.parametrize("encrypted", (False, True))
def test_malformed_startup_remains_a_worker_failure(wires, monkeypatch, encrypted):
    wire = wires(encrypted=encrypted)
    entered = Event()
    actual = wire.proxy._connection
    def connection(*args):
        entered.set()
        actual(*args)
    monkeypatch.setattr(wire.proxy, "_connection", connection)
    wire.connect(startup=struct.pack("!II", 7, 196608))
    assert entered.wait(2)
    wire.proxy.workers[0].join(2)
    with pytest.raises(BaseExceptionGroup) as caught:
        wire.finish()
    assert len(_leaves(caught.value)) == 1
    assert type(_leaves(caught.value)[0]) is AssertionError


def test_worker_socket_cleanup_failure_is_retained_after_owners_join(wires, monkeypatch):
    wire = wires()
    client = wire.connect()
    client.sendall(_query())
    assert _exact(client, len(_query())) == _query()
    actual = wire.proxy._close
    failure = AssertionError("explicit failure after real worker close")
    def close(connection):
        actual(connection)
        if isinstance(connection, ssl.SSLSocket) and current_thread().name.startswith("physical-fault-"):
            raise failure
    monkeypatch.setattr(wire.proxy, "_close", close)
    with pytest.raises(BaseExceptionGroup) as caught:
        wire.finish()
    assert _leaves(caught.value) == [failure]
    assert not any(worker.is_alive() for worker in wire.proxy.workers)


def test_incomplete_tls_handshake_is_registered_and_woken_on_stop(wires, monkeypatch):
    wire = wires()
    registered = Event()
    remember = wire.proxy._remember
    def track(connection):
        result = remember(connection)
        if isinstance(connection, ssl.SSLSocket):
            registered.set()
        return result
    monkeypatch.setattr(wire.proxy, "_remember", track)
    client = socket.create_connection(("127.0.0.1", wire.proxy.port), 3)
    wire.clients.append(client)
    client.sendall(SSL_REQUEST)
    assert _exact(client, 1) == b"S" and registered.wait(2)
    wire.finish()
    assert not wire.proxy.failures


@pytest.mark.parametrize("registration", ("accepted", "wrapped", "upstream"))
def test_socket_registered_after_stop_is_woken_and_closed(wires, monkeypatch, registration):
    wire = wires()
    waiting, proceed = Event(), Event()
    remember, errors, client_errors = wire.proxy._remember, [], []
    def track(connection):
        current = "wrapped" if isinstance(connection, ssl.SSLSocket) else (
            "accepted" if not wire.proxy.sockets else "upstream"
        )
        if current == registration:
            waiting.set()
            assert proceed.wait(2)
        return remember(connection)
    def connect():
        try:
            wire.connect()
        except (OSError, EOFError) as failure:
            client_errors.append(failure)
    monkeypatch.setattr(wire.proxy, "_remember", track)
    client_thread = Thread(target=connect, name="proxy-test-client")
    client_thread.start()
    closing = Thread(target=_closing, args=(wire, errors), name="proxy-test-close")
    try:
        assert waiting.wait(2)
        closing.start()
        assert wire.proxy.stop.wait(2)
    finally:
        proceed.set()
        if closing.ident is not None:
            closing.join(2)
        client_thread.join(2)
    assert not closing.is_alive() and not client_thread.is_alive()
    assert not errors and not wire.proxy.failures
    assert all(c.fileno() == -1 for c in wire.proxy.sockets)
