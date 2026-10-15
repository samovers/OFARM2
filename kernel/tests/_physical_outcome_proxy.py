"""Owned multi-connection wire faults over the actual isolated PostgreSQL.

This fixture may terminate local TLS. Upstream plaintext is explicitly confined
to the owned disposable loopback server. It preserves real backend selection for
an entire transaction, and neither substitutes transactions nor proves topology.
"""
from __future__ import annotations

import select
import socket
import struct
from threading import Event, Lock, Thread

from psycopg.conninfo import conninfo_to_dict, make_conninfo

from kernel.tests._signing_observation_proxy import _startup


def stage(query):
    text = b" ".join(query.upper().split())
    if not text:
        return "probe"
    if text.startswith(b"BEGIN"):
        return "begin"
    if b"STATEMENT_TIMEOUT" in text:
        return "timeouts"
    if b"CREATE_TENANT_CHALLENGE" in text:
        return "challenge"
    if b"CURRENT_TENANT_CHALLENGE" in text:
        return "challenge_read"
    if b"BIND_TENANT_CAPABILITY" in text:
        return "bind"
    if b"CURRENT_TENANT_CONTEXT" in text:
        return "context"
    if b"PG_XACT_STATUS" in text:
        return "status"
    if text.startswith(b"SELECT") and b"GOVERNED_WRITE_BATCH" in text:
        return "batch"
    if text == b"ROLLBACK":
        return "rollback"
    if text == b"COMMIT":
        return "commit"
    return "other"


class PhysicalWireProxy:
    """Lose first real COMMIT reply, then optionally stall one observer phase."""

    def __init__(self, dsn, *, fault=None, partial=False, hold_commit=False,
                 tls=None, certificate=None, on_commit=None):
        self.source = conninfo_to_dict(dsn)
        self.on_commit = on_commit
        self.fault = fault
        self.partial = partial
        self.hold_commit = hold_commit
        self.tls, self.certificate = tls, certificate
        self.stop = Event()
        self.ambiguous = Event()
        self.withheld = Event()
        self.release = Event()
        self.eventual = Event()
        self.statements = []
        self.results = []
        self.failures = []
        self.sockets = []
        self.workers = []
        self._lock = Lock()
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()
        self.listener.settimeout(0.1)
        self.port = self.listener.getsockname()[1]
        self.thread = Thread(target=self._serve, name="physical-fault-listener")

    @property
    def dsn(self):
        values = dict(self.source)
        values.update(host="127.0.0.1", hostaddr="127.0.0.1", port=str(self.port),
                      sslmode="disable", gssencmode="disable", sslcertmode="disable")
        if self.tls:
            values.update(host="signing.test", sslmode="verify-full",
                          sslrootcert=str(self.certificate))
        return make_conninfo(**values)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_exc):
        self.stop.set()
        self.release.set()
        self.listener.close()
        self.thread.join(2)
        with self._lock:
            for connection in self.sockets:
                self._shutdown(connection)
        for worker in self.workers:
            worker.join(2)
        for connection in self.sockets:
            self._close(connection)
        assert not self.thread.is_alive()
        assert not any(worker.is_alive() for worker in self.workers)
        if self.failures:
            failures = list(self.failures)
            if _exc[1] is not None:
                failures.insert(0, _exc[1])
            raise BaseExceptionGroup("physical wire proxy failed", failures)

    def _remember(self, connection):
        with self._lock:
            self.sockets.append(connection)
            if self.stop.is_set():
                self._shutdown(connection)
        return connection

    @staticmethod
    def _shutdown(connection):
        try:
            # Wake a worker without clearing SSLSocket._sslobj before its recv.
            socket.socket.shutdown(connection, socket.SHUT_RDWR)
        except OSError:
            pass

    @staticmethod
    def _close(connection):
        PhysicalWireProxy._shutdown(connection)
        connection.close()

    def _serve(self):
        while not self.stop.is_set():
            try:
                client, _ = self.listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            self._remember(client)
            number = len(self.workers) + 1
            worker = Thread(target=self._connection, args=(client, number),
                            name=f"physical-fault-{number}")
            self.workers.append(worker)
            worker.start()

    def _connection(self, client, number):
        upstream = None
        try:
            client.settimeout(3)
            startup = _startup(client)
            if struct.unpack("!I", startup[4:8])[0] == 80877103:
                assert self.tls is not None
                client.sendall(b"S")
                client = self.tls.wrap_socket(
                    client, server_side=True, do_handshake_on_connect=False,
                )
                self._remember(client)
                client.do_handshake()
                startup = _startup(client)
            host = self.source.get("hostaddr") or self.source["host"]
            upstream = socket.create_connection((host, int(self.source["port"])), 3)
            self._remember(upstream)
            upstream.sendall(startup)
            self._relay(client, upstream, number)
        except (OSError, EOFError):
            # Closing a client is the intended fault/disposal observation.
            pass
        except BaseException as failure:
            if not any(failure is recorded for recorded in self.failures):
                self.failures.append(failure)
        finally:
            for connection in (upstream, client):
                if connection is not None:
                    try:
                        self._close(connection)
                    except BaseException as failure:
                        self.failures.append(failure)

    def _relay(self, client, upstream, number):
        buffers = {client: bytearray(), upstream: bytearray()}
        current = "startup"
        observer = False
        while not self.stop.is_set():
            ready, _, _ = select.select([client, upstream], [], [], 0.02)
            for source in ready:
                part = source.recv(65536)
                if not part:
                    return
                buffers[source].extend(part)
                buffer = buffers[source]
                while len(buffer) >= 5:
                    size = struct.unpack("!I", buffer[1:5])[0] + 1
                    assert 5 <= size <= 1048576
                    if len(buffer) < size:
                        break
                    packet = bytes(buffer[:size])
                    del buffer[:size]
                    kind = packet[:1]
                    if source is client:
                        if kind in (b"P", b"Q"):
                            query = packet[5:].split(b"\0")[kind == b"P"]
                            current = stage(query)
                            observer = self.ambiguous.is_set()
                            with self._lock:
                                self.statements.append((number, current, query, observer))
                            if current == "commit" and not observer and self.hold_commit:
                                self.ambiguous.set()
                                self._close(client)
                                self.release.wait(15)
                                if self.stop.is_set():
                                    return
                                upstream.sendall(packet)
                                # The backend still owns the original transaction.
                                self._drain_commit(upstream)
                                self.eventual.set()
                                return
                        upstream.sendall(packet)
                        continue
                    if current == "commit" and not observer and kind == b"C":
                        if self.on_commit is not None:
                            try:
                                self.on_commit()
                            except BaseException as failure:
                                self.failures.append(failure)
                                raise
                        self.ambiguous.set()
                        self._close(client)
                        return
                    if observer and current == self.fault:
                        self.results.append((current, kind))
                        if not self.partial or kind == b"Z":
                            self.withheld.set()
                            self.stop.wait(15)
                            return
                    client.sendall(packet)

    @staticmethod
    def _drain_commit(upstream):
        buffer = bytearray()
        while True:
            buffer.extend(upstream.recv(65536))
            while len(buffer) >= 5:
                size = struct.unpack("!I", buffer[1:5])[0] + 1
                if len(buffer) < size:
                    break
                packet = bytes(buffer[:size])
                del buffer[:size]
                if packet[:1] == b"Z":
                    assert packet[-1:] == b"I"
                    return
