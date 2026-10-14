"""Test-owned wire fault proxy; it never substitutes database authority."""
from __future__ import annotations

import os
import select
import socket
import ssl
import struct
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from psycopg.conninfo import conninfo_to_dict, make_conninfo


def tls_context(directory: Path) -> tuple[ssl.SSLContext, Path]:
    """Generate an ephemeral local test CA/server identity, never a live key."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "signing.test")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("signing.test")]), False)
        .sign(key, hashes.SHA256())
    )
    certificate = directory / "signing-test-ca.pem"
    private = directory / "signing-test-key.pem"
    certificate.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    private.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    private.chmod(0o600)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate, private)
    return context, certificate


def _exact(connection: socket.socket, length: int) -> bytes:
    result = bytearray()
    while len(result) < length:
        part = connection.recv(length - len(result))
        if not part:
            raise EOFError("test peer closed")
        result.extend(part)
    return bytes(result)


def _startup(connection: socket.socket) -> bytes:
    length = _exact(connection, 4)
    size = struct.unpack("!I", length)[0]
    assert 8 <= size <= 65536
    return length + _exact(connection, size - 4)


class WireFaultProxy:
    """Forward real PostgreSQL messages, selectively withholding completion.

    Threads and sockets belong only to the fixture and are joined/closed on exit.
    The production reader still owns and disposes its independent client socket.
    TLS, when enabled, terminates at this controlled fault peer; upstream authority
    remains the real PostgreSQL function and role, not a stand-in protocol server.
    """

    def __init__(self, dsn: str, mode: str, *, tls=None, certificate=None):
        self.source = conninfo_to_dict(dsn)
        self.mode = mode
        self.tls = tls
        self.certificate = certificate
        self.stop = threading.Event()
        self.query_seen = threading.Event()
        self.withheld = threading.Event()
        self.accepted = 0
        self.backend_types: list[bytes] = []
        self.frontend_types: list[bytes] = []
        self.statements: list[bytes] = []
        self.tls_version = None
        self.result_packets = []
        self.failure: BaseException | None = None
        self.sockets: list[socket.socket] = []
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()
        self.listener.settimeout(0.1)
        self.port = self.listener.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, name="signing-test-proxy")

    @property
    def dsn(self) -> str:
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
        self.listener.close()
        for connection in self.sockets:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()
        self.thread.join(2)
        assert not self.thread.is_alive(), "test proxy worker survived cleanup"
        if self.failure is not None:
            raise AssertionError("test proxy failed") from self.failure

    def _serve(self):
        try:
            while not self.stop.is_set():
                try:
                    client, _address = self.listener.accept()
                    break
                except TimeoutError:
                    continue
            else:
                return
            self.accepted += 1
            self.sockets.append(client)
            client.settimeout(2)
            startup = _startup(client)
            if struct.unpack("!I", startup[4:8])[0] == 80877103:
                assert self.tls is not None
                client.sendall(b"S")
                if self.mode == "tls-handshake":
                    self.withheld.set()
                    return self.stop.wait(10)
                client = self.tls.wrap_socket(client, server_side=True)
                self.sockets.append(client)
                self.tls_version = client.version()
                startup = _startup(client)
            host = self.source.get("hostaddr") or self.source["host"]
            port = int(self.source["port"])
            if host.startswith("/"):
                upstream = socket.socket(socket.AF_UNIX)
                upstream.settimeout(2)
                upstream.connect(f"{host}/.s.PGSQL.{port}")
            else:
                upstream = socket.create_connection((host, port), timeout=2)
            self.sockets.append(upstream)
            upstream.sendall(startup)
            self._relay(client, upstream)
        except (OSError, EOFError) as exc:
            if not self.stop.is_set() and not self.withheld.is_set():
                self.failure = exc
        except BaseException as exc:
            self.failure = exc

    def _relay(self, client, upstream):
        buffers = {client: bytearray(), upstream: bytearray()}
        while not self.stop.is_set():
            if self.mode == "startup":
                self.withheld.set()
            readers = [] if self.withheld.is_set() else [client, upstream]
            ready, _, _ = select.select(readers, [], [], 0.01)
            for source in ready:
                part = source.recv(65536)
                if not part:
                    return
                buffer = buffers[source]
                buffer.extend(part)
                while len(buffer) >= 5:
                    size = struct.unpack("!I", buffer[1:5])[0] + 1
                    assert 5 <= size <= 1048576
                    if len(buffer) < size:
                        break
                    packet = bytes(buffer[:size])
                    del buffer[:size]
                    kind = packet[:1]
                    if source is client:
                        self.frontend_types.append(kind)
                        if kind in (b"P", b"Q"):
                            self.statements.append(packet)
                            self.query_seen.set()
                        upstream.sendall(packet)
                        continue
                    self.backend_types.append(kind)
                    if self.query_seen.is_set():
                        if kind in (b"T", b"D", b"C"):
                            self.result_packets.append(packet)
                        if self.mode == "reply" or (self.mode == "ready" and kind == b"Z"):
                            self.withheld.set()
                            return self.stop.wait(10)
                        if self.mode == "nonidle" and kind == b"Z":
                            packet = packet[:-1] + b"T"
                        if self.mode == "extra-result" and kind == b"C":
                            client.sendall(packet)
                            for result in self.result_packets:
                                client.sendall(result)
                            continue
                        if self.mode == "fatal" and kind == b"C":
                            body = b"SFATAL\0VFATAL\0CXX000\0Mfixture fatal after real row\0\0"
                            packet = b"E" + struct.pack("!I", len(body) + 4) + body
                        if self.mode == "malformed" and kind == b"D":
                            # Corrupt only the real first UUID scalar; leave framing valid.
                            length = struct.unpack("!i", packet[7:11])[0]
                            body = packet[5:7] + struct.pack("!i", 7) + b"notuuid" + packet[11 + length:]
                            packet = b"D" + struct.pack("!I", len(body) + 4) + body
                        if self.mode == "duplicate" and kind == b"D":
                            client.sendall(packet)
                        if self.mode == "null" and kind == b"D":
                            count = struct.unpack("!H", packet[5:7])[0]
                            body = struct.pack("!H", count) + struct.pack("!i", -1) * count
                            packet = b"D" + struct.pack("!I", len(body) + 4) + body
                        if self.mode == "columns" and kind == b"T":
                            # Same-length name corruption preserves protocol shape.
                            packet = packet.replace(b"binder_instance_id\0", b"wrongx_instance_id\0", 1)
                    client.sendall(packet)


def saturate_client_send_queue(descriptor: int) -> int:
    """Inject backpressure only into the test TLS peer, before native finish.

    The proxy has stopped reading this connection. No bytes are forwarded to the
    database. The duplicate descriptor is fixture-owned and closed before return.
    """
    total = 0
    started = time.monotonic()
    with socket.socket(fileno=os.dup(descriptor)) as duplicate:
        duplicate.setblocking(False)
        duplicate.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
        while total < 16 * 1024 * 1024 and time.monotonic() - started < 0.5:
            try:
                total += duplicate.send(b"fault-peer-backpressure" * 2048)
            except BlockingIOError:
                assert total > 0
                return total
    raise AssertionError("test could not establish client socket backpressure")
