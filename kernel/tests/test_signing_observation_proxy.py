"""SP01–SP03: real socket/TLS lifecycle controls, not database authority."""
from __future__ import annotations

import inspect
from pathlib import Path
import socket
import ssl
import struct
import sys
import tempfile
from threading import Event, Thread, current_thread

import pytest

from kernel.tests._signing_observation_proxy import (
    WireFaultProxy, _exact, _startup, tls_context,
)


STARTUP = struct.pack("!II", 8, 196608)
SSL_REQUEST = struct.pack("!II", 8, 80877103)
QUERY = b"Q" + struct.pack("!I", 13) + b"SELECT 1\0"
READY = b"Z" + struct.pack("!I", 5) + b"I"
TLS_VERSIONS = (ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3)


class _Wire:
    """Own one real proxy and a local packet echo peer, never PostgreSQL."""

    def __init__(self, directory, *, version=None, mode="forward", unix=False):
        self.version = version
        self.stop, self.started, self.received = Event(), Event(), Event()
        self.sockets, self.clients, self.errors, self.packets = [], [], [], []
        self.closed = False
        self.unix_directory = tempfile.TemporaryDirectory(prefix="signing-wire-") if unix else None
        self.listener = socket.socket(socket.AF_UNIX if unix else socket.AF_INET)
        if unix:
            self.listener.bind(str(Path(self.unix_directory.name) / ".s.PGSQL.5432"))
            dsn = f"host={self.unix_directory.name} port=5432 dbname=fixture user=fixture"
        else:
            self.listener.bind(("127.0.0.1", 0))
            dsn = f"host=127.0.0.1 port={self.listener.getsockname()[1]} dbname=fixture user=fixture"
        self.listener.listen()
        self.listener.settimeout(.1)
        context, self.certificate = tls_context(directory) if version else (None, None)
        if context:
            context.minimum_version = context.maximum_version = version
        self.proxy = WireFaultProxy(dsn, mode, tls=context, certificate=self.certificate)
        self.peer = Thread(target=self._serve, name="signing-wire-peer")
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
            connection.settimeout(2)
            assert _startup(connection) == STARTUP
            self.started.set()
            while not self.stop.is_set():
                header = _exact(connection, 5)
                packet = header + _exact(connection, struct.unpack("!I", header[1:])[0] - 4)
                self.packets.append(packet)
                self.received.set()
                connection.sendall(packet + READY)
        except EOFError:
            pass
        except OSError as failure:
            if not self.stop.is_set() and not self.proxy.stop.is_set():
                self.errors.append(failure)
        except BaseException as failure:
            self.errors.append(failure)
        finally:
            for connection in self.sockets:
                connection.close()

    def raw_client(self):
        client = socket.create_connection(("127.0.0.1", self.proxy.port), 2)
        self.clients.append(client)
        return client

    def connect(self, startup=STARTUP):
        client = self.raw_client()
        if self.version:
            client.sendall(SSL_REQUEST)
            assert _exact(client, 1) == b"S"
            context = ssl.create_default_context(cafile=str(self.certificate))
            context.minimum_version = context.maximum_version = self.version
            client = context.wrap_socket(client, server_hostname="signing.test")
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
                try:
                    socket.socket.shutdown(connection, socket.SHUT_RDWR)
                except OSError:
                    pass
                connection.close()
            self.peer.join(2)
            assert not self.peer.is_alive()
            assert not self.proxy.thread.is_alive()
            assert not self.errors, self.errors
            assert all(c.fileno() == -1 for c in [*self.clients, *self.sockets, *self.proxy.sockets])
            if self.unix_directory:
                self.unix_directory.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, _kind, body, _trace):
        self.finish(body)


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


def _trace_worker(monkeypatch, trace, finished=None):
    serve = WireFaultProxy._serve
    def traced(self):
        sys.settrace(trace)
        try:
            serve(self)
        finally:
            sys.settrace(None)
            if finished:
                finished.set()
    monkeypatch.setattr(WireFaultProxy, "_serve", traced)


def _relay_line(fragment):
    lines, start = inspect.getsourcelines(WireFaultProxy._relay)
    return next(start + i for i, line in enumerate(lines) if fragment in line)


@pytest.mark.parametrize("version", (None, *TLS_VERSIONS))
@pytest.mark.parametrize("unix", (False, True))
def test_sp02_normal_forwarding_and_owned_disposal(wires, version, unix):
    wire = wires(version=version, unix=unix)
    client = wire.connect()
    client.sendall(QUERY)
    assert _exact(client, len(QUERY)) == QUERY
    assert wire.received.wait(2) and wire.packets == [QUERY]
    wire.finish()
    assert wire.proxy.failure is None


@pytest.mark.parametrize("version", TLS_VERSIONS)
def test_sp01_neutral_wake_seam_preserves_tls_and_forwards_plaintext(wires, monkeypatch, version):
    waiting, allow_read, processed = Event(), Event(), Event()
    facts, errors = {}, []
    recv_line = _relay_line("part = source.recv")
    forwarded_line = _relay_line("upstream.sendall(packet)") + 1
    def trace(frame, event, _arg):
        if event == "line" and frame.f_code is WireFaultProxy._relay.__code__:
            if isinstance(frame.f_locals.get("source"), ssl.SSLSocket):
                if frame.f_lineno == recv_line:
                    waiting.set()
                    assert allow_read.wait(2)
                if frame.f_lineno == recv_line + 1:
                    facts["plaintext"] = frame.f_locals["part"]
                if frame.f_lineno == forwarded_line:
                    processed.set()
        return trace
    _trace_worker(monkeypatch, trace, processed)
    native_shutdown = socket.socket.shutdown
    def shutdown(connection, how):
        if (isinstance(connection, ssl.SSLSocket) and connection in wire.proxy.sockets
                and connection.fileno() >= 0 and current_thread().name == "signing-test-close"):
            facts["tls_preserved"] = connection._sslobj is not None
            allow_read.set()
            assert processed.wait(2)
        return native_shutdown(connection, how)
    monkeypatch.setattr(socket.socket, "shutdown", shutdown)
    wire = wires(version=version)
    client = wire.connect()
    assert wire.started.wait(2)
    client.sendall(QUERY)
    assert waiting.wait(2)
    closing = Thread(target=_closing, args=(wire, errors), name="signing-test-close")
    try:
        closing.start()
        closing.join(2)
    finally:
        allow_read.set()
        closing.join(2)
    assert not closing.is_alive() and not errors, errors
    assert facts == {"tls_preserved": True, "plaintext": QUERY}
    assert wire.received.wait(2) and wire.packets == [QUERY]
    assert wire.proxy.frontend_types == [b"Q"] and wire.proxy.statements == [QUERY]


@pytest.mark.parametrize("version", (None, *TLS_VERSIONS))
def test_sp02_worker_reenters_select_before_final_close(wires, monkeypatch, version):
    waiting, resume = Event(), Event()
    selected_fds = []
    select_line = _relay_line("ready, _, _ = select.select")
    def trace(frame, event, _arg):
        if (event == "line" and frame.f_code is WireFaultProxy._relay.__code__
                and frame.f_lineno == select_line):
            waiting.set()
            assert resume.wait(2)
            selected_fds.extend(c.fileno() for c in frame.f_locals["readers"])
        return trace
    _trace_worker(monkeypatch, trace)
    wire = wires(version=version)
    wire.connect()
    assert waiting.wait(2)
    original_join = wire.proxy.thread.join
    def join(timeout):
        resume.set()
        original_join(timeout)
    monkeypatch.setattr(wire.proxy.thread, "join", join)
    try:
        wire.finish()
    finally:
        resume.set()
    assert selected_fds and all(fd >= 0 for fd in selected_fds)
    assert wire.proxy.failure is None


@pytest.mark.parametrize("stage", ("accept", "startup", "handshake", "relay"))
def test_sp02_stop_interrupts_each_owned_blocking_stage(wires, monkeypatch, stage):
    registered = Event()
    remember = WireFaultProxy._remember
    def track(self, connection):
        remember(self, connection)
        if isinstance(connection, ssl.SSLSocket) if stage == "handshake" else True:
            registered.set()
    monkeypatch.setattr(WireFaultProxy, "_remember", track)
    wire = wires(version=TLS_VERSIONS[1] if stage == "handshake" else None)
    if stage == "startup":
        wire.raw_client().sendall(STARTUP[:2])
        assert registered.wait(2)
    elif stage == "handshake":
        client = wire.raw_client()
        client.sendall(SSL_REQUEST)
        assert _exact(client, 1) == b"S" and registered.wait(2)
    elif stage == "relay":
        wire.connect()
        assert wire.started.wait(2)
    wire.finish()
    assert wire.proxy.failure is None


@pytest.mark.parametrize("mode", ("startup", "tls-handshake", "reply", "ready"))
def test_sp02_withholding_remains_stop_driven(wires, mode):
    wire = wires(mode=mode, version=TLS_VERSIONS[1] if mode == "tls-handshake" else None)
    if mode == "tls-handshake":
        client = wire.raw_client()
        client.sendall(SSL_REQUEST)
        assert _exact(client, 1) == b"S"
    else:
        client = wire.connect()
        if mode != "startup":
            client.sendall(QUERY)
    assert wire.proxy.withheld.wait(2)
    wire.finish()
    assert wire.proxy.failure is None


@pytest.mark.parametrize("registration", ("accepted", "wrapped", "upstream"))
def test_sp02_late_registration_is_woken_and_closed(wires, monkeypatch, registration):
    waiting, proceed = Event(), Event()
    errors, client_errors, acquired = [], [], []
    remember = WireFaultProxy._remember
    def track(self, connection):
        current = "wrapped" if isinstance(connection, ssl.SSLSocket) else (
            "accepted" if not self.sockets else "upstream"
        )
        acquired.append(connection)
        if current == registration:
            waiting.set()
            assert proceed.wait(2)
        remember(self, connection)
    monkeypatch.setattr(WireFaultProxy, "_remember", track)
    wire = wires(version=TLS_VERSIONS[1])
    def connect():
        try:
            wire.connect()
        except (OSError, EOFError) as failure:
            client_errors.append(failure)
    client_thread = Thread(target=connect, name="signing-test-client")
    client_thread.start()
    closing = Thread(target=_closing, args=(wire, errors), name="signing-test-close")
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
    assert not errors and wire.proxy.failure is None, errors
    assert acquired and all(c.fileno() == -1 for c in acquired)


@pytest.mark.parametrize("registration", ("accepted", "wrapped", "upstream"))
def test_sp02_failed_registration_retains_local_owner(wires, monkeypatch, registration):
    acquired = []
    failure = AssertionError("registration failure")
    remember = WireFaultProxy._remember
    def register(self, connection):
        current = "wrapped" if isinstance(connection, ssl.SSLSocket) else (
            "accepted" if not self.sockets else "upstream"
        )
        acquired.append(connection)
        if current == registration:
            raise failure
        remember(self, connection)
    monkeypatch.setattr(WireFaultProxy, "_remember", register)
    wire = wires(version=TLS_VERSIONS[1])
    try:
        wire.connect()
    except (OSError, EOFError):
        pass
    wire.proxy.thread.join(2)
    with pytest.raises(BaseExceptionGroup) as caught:
        wire.finish()
    assert _leaves(caught.value) == [failure]
    assert acquired and all(c.fileno() == -1 for c in acquired)


def test_sp02_unix_connect_failure_closes_created_socket(wires, monkeypatch):
    failure, connecting = OSError("Unix connect failure"), []
    connect = socket.socket.connect
    def fail(connection, address):
        if connection.family == socket.AF_UNIX:
            connecting.append(connection)
            raise failure
        return connect(connection, address)
    wire = wires(unix=True)
    monkeypatch.setattr(socket.socket, "connect", fail)
    wire.connect()
    wire.proxy.thread.join(2)
    with pytest.raises(BaseExceptionGroup) as caught:
        wire.finish()
    assert _leaves(caught.value) == [failure]
    assert len(connecting) == 1 and connecting[0] in wire.proxy.sockets
    assert connecting[0].fileno() == -1


@pytest.mark.parametrize("stage", ("tcp", "wrap"))
def test_sp02_acquisition_failure_keeps_previous_owner(wires, monkeypatch, stage):
    failure = OSError("acquisition failed")
    wire = wires(version=TLS_VERSIONS[1] if stage == "wrap" else None)
    if stage == "tcp":
        create = socket.create_connection
        def fail(address, *args, **kwargs):
            if address[1] == int(wire.proxy.source["port"]):
                raise failure
            return create(address, *args, **kwargs)
        monkeypatch.setattr(socket, "create_connection", fail)
    else:
        def fail(*args, **kwargs):
            raise failure
        monkeypatch.setattr(wire.proxy.tls, "wrap_socket", fail)
    try:
        wire.connect()
    except (OSError, EOFError):
        pass
    wire.proxy.thread.join(2)
    with pytest.raises(BaseExceptionGroup) as caught:
        wire.finish()
    assert _leaves(caught.value) == [failure]


@pytest.mark.parametrize("version", (None, *TLS_VERSIONS))
@pytest.mark.parametrize("malformed", ("startup", "frame"))
def test_sp03_malformed_input_retains_original_worker_traceback(wires, version, malformed):
    wire = wires(version=version)
    client = wire.connect(startup=struct.pack("!II", 7, 196608) if malformed == "startup" else STARTUP)
    if malformed == "frame":
        assert wire.started.wait(2)
        client.sendall(b"Q" + struct.pack("!I", 1048576))
    wire.proxy.thread.join(2)
    original = wire.proxy.failure
    assert type(original) is AssertionError
    with pytest.raises(BaseExceptionGroup) as caught:
        wire.finish()
    assert _leaves(caught.value) == [original]
    frames, trace = [], original.__traceback__
    while trace:
        frames.append(trace.tb_frame.f_code.co_name)
        trace = trace.tb_next
    assert ("_startup" if malformed == "startup" else "_relay") in frames


@pytest.mark.parametrize("body", (ValueError("body"), KeyboardInterrupt("body")))
def test_sp03_body_only_propagates_unchanged(wires, body):
    wire = wires()
    with pytest.raises(type(body)) as caught:
        with wire:
            raise body
    assert caught.value is body and wire.proxy.failure is None


@pytest.mark.parametrize("error_type", (OSError, EOFError, KeyboardInterrupt))
@pytest.mark.parametrize("condition", ("running", "stop", "withheld"))
def test_sp03_only_existing_stop_io_is_suppressed(wires, monkeypatch, error_type, condition):
    failure, entered, release = error_type("worker error"), Event(), Event()
    def relay(self, *_args):
        if condition == "withheld":
            self.withheld.set()
        entered.set()
        assert release.wait(2)
        raise failure
    monkeypatch.setattr(WireFaultProxy, "_relay", relay)
    wire = wires()
    wire.connect()
    assert entered.wait(2)
    if condition == "stop":
        join = wire.proxy.thread.join
        def release_at_join(timeout):
            assert wire.proxy.stop.is_set()
            release.set()
            join(timeout)
        monkeypatch.setattr(wire.proxy.thread, "join", release_at_join)
    else:
        release.set()
        wire.proxy.thread.join(2)
    try:
        if condition == "running" or error_type is KeyboardInterrupt:
            with pytest.raises(BaseExceptionGroup) as caught:
                wire.finish()
            assert _leaves(caught.value) == [failure]
        else:
            wire.finish()
            assert wire.proxy.failure is None
    finally:
        release.set()


def test_sp03_body_worker_and_cleanup_failures_are_all_retained(wires, monkeypatch):
    worker_error = AssertionError("genuine worker error before stop")
    cleanup_error = KeyboardInterrupt("worker disposal error")
    body_error = ValueError("test body error")
    recorded = Event()
    retain, close = WireFaultProxy._retain_failure, WireFaultProxy._close
    closed = []
    def relay(*_args):
        raise worker_error
    def record(self, failure):
        retain(self, failure)
        if failure is worker_error:
            recorded.set()
            assert self.stop.wait(2)
    def dispose(connection):
        close(connection)
        if current_thread().name == "signing-test-proxy":
            closed.append(connection)
            if len(closed) == 1:
                raise cleanup_error
    monkeypatch.setattr(WireFaultProxy, "_relay", relay)
    monkeypatch.setattr(WireFaultProxy, "_retain_failure", record)
    monkeypatch.setattr(WireFaultProxy, "_close", staticmethod(dispose))
    wire = wires()
    wire.connect()
    assert recorded.wait(2)
    with pytest.raises(BaseExceptionGroup) as caught:
        wire.finish(body_error)
    assert _leaves(caught.value) == [body_error, worker_error, cleanup_error]
    assert len(closed) == 2 and all(c.fileno() == -1 for c in closed)


@pytest.mark.parametrize("operation", ("listener", "wake", "join", "close"))
def test_sp03_teardown_failure_cannot_skip_remaining_disposal(wires, monkeypatch, operation):
    failure, injected = RuntimeError("teardown error"), []
    wire = wires()
    client = wire.connect()
    client.sendall(QUERY)
    assert _exact(client, len(QUERY)) == QUERY
    if operation == "listener":
        close = socket.socket.close
        def fail(connection):
            close(connection)
            if connection is wire.proxy.listener and not injected:
                injected.append(connection)
                raise failure
        monkeypatch.setattr(socket.socket, "close", fail)
    elif operation == "join":
        join = wire.proxy.thread.join
        def fail(timeout):
            join(timeout)
            injected.append(timeout)
            raise failure
        monkeypatch.setattr(wire.proxy.thread, "join", fail)
    else:
        name = "_shutdown" if operation == "wake" else "_close"
        actual = getattr(wire.proxy, name)
        def fail(connection):
            actual(connection)
            if current_thread().name == "MainThread" and not injected:
                injected.append(connection)
                raise failure
        monkeypatch.setattr(wire.proxy, name, fail)
    with pytest.raises(BaseExceptionGroup) as caught:
        wire.finish()
    assert _leaves(caught.value) == [failure] and injected


def test_sp03_failed_worker_wake_still_closes_owned_socket(wires, monkeypatch):
    failure, affected = RuntimeError("native wake error"), []
    shutdown = WireFaultProxy._shutdown
    def wake(connection):
        shutdown(connection)
        if current_thread().name == "signing-test-proxy" and not affected:
            affected.append(connection)
            raise failure
    monkeypatch.setattr(WireFaultProxy, "_shutdown", staticmethod(wake))
    wire = wires()
    wire.connect()
    assert wire.started.wait(2)
    with pytest.raises(BaseExceptionGroup) as caught:
        wire.finish()
    assert _leaves(caught.value) == [failure]
    assert len(affected) == 1 and affected[0].fileno() == -1


def test_sp03_simultaneous_wake_and_close_failures_keep_context_and_later_owners(wires, monkeypatch):
    worker_error = AssertionError("primary worker failure")
    wake_error, close_error = OSError("wake failure"), RuntimeError("close failure")
    body_error = ValueError("body failure")
    affected, closed = [], []
    shutdown, close = WireFaultProxy._shutdown, socket.socket.close
    def relay(*_args):
        raise worker_error
    def wake(connection):
        shutdown(connection)
        if current_thread().name == "signing-test-proxy" and not affected:
            affected.append(connection)
            raise wake_error
    def dispose(connection):
        close(connection)
        if current_thread().name == "signing-test-proxy":
            closed.append(connection)
            if affected and connection is affected[0]:
                raise close_error
    monkeypatch.setattr(WireFaultProxy, "_relay", relay)
    monkeypatch.setattr(WireFaultProxy, "_shutdown", staticmethod(wake))
    monkeypatch.setattr(socket.socket, "close", dispose)
    wire = wires()
    wire.connect()
    wire.proxy.thread.join(2)
    with pytest.raises(BaseExceptionGroup) as caught:
        wire.finish(body_error)
    assert _leaves(caught.value) == [body_error, worker_error, close_error]
    assert close_error.__context__ is wake_error
    assert len(closed) == 2 and all(c.fileno() == -1 for c in closed)


def test_sp03_stop_precedes_blocking_registration_lock(wires, monkeypatch):
    wire = wires()
    actual = wire.proxy._lock
    class ObservedLock:
        def __enter__(self):
            assert wire.proxy.stop.is_set()
            actual.acquire()
        def __exit__(self, *_args):
            actual.release()
    monkeypatch.setattr(wire.proxy, "_lock", ObservedLock())
    wire.finish()
