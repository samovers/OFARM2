"""H1 configuration and disposable signing-observation I/O; no authority policy."""
from __future__ import annotations

import ipaddress
import os
import stat
from pathlib import Path

import psycopg
from psycopg import pq
from psycopg.conninfo import make_conninfo
from psycopg.waiting import Wait

from .postgres_wait import checkpoint, disposing, wait
from .signing_receipt import SIGNING_EVIDENCE_MAX_BYTES


class SigningObservationConfigError(ValueError):
    pass


def _numeric_host_mismatch(host: str, address: str) -> bool:
    try:
        numeric_host = ipaddress.ip_address(host)
    except ValueError:
        return False
    return numeric_host != ipaddress.ip_address(address)


def _prepared_options(dsn: str) -> dict[str, str]:
    env = dict(os.environ)
    if any(k in env for k in ("PGSERVICE", "PGSERVICEFILE", "PGSYSCONFDIR", "PGREQUIRESSL")):
        raise ValueError("service or legacy expansion")
    options = pq.Conninfo.parse(dsn.encode())
    explicit = {o.keyword.decode(): o.val.decode() for o in options if o.val is not None}
    values = {}
    for option in options:
        name = option.keyword.decode()
        value = explicit.get(name, env.get((option.envvar or b"").decode()))
        if value is None and option.compiled is not None:
            value = option.compiled.decode()
        if value is not None:
            values[name] = value
    host, address, port = (explicit.get(k, "") for k in ("host", "hostaddr", "port"))
    if (
        not (host or address) or not port.isascii() or not port.isdigit()
        or not 1 <= int(port) <= 65535
        or any("," in v for v in (host, address, port))
        or any(k in explicit and not explicit[k] for k in ("host", "hostaddr", "port"))
        or values.get("host", "") != host or values.get("hostaddr", "") != address
        or "service" in values or not values.get("user")
    ):
        raise ValueError("route or credentials are not explicit")
    if address:
        ipaddress.ip_address(address)
        if host.startswith("/") or _numeric_host_mismatch(host, address):
            raise ValueError("paired host and address differ")
    elif not host.startswith("/"):
        ipaddress.ip_address(host)
    auth = values.get("require_auth", "none,password,md5,scram-sha-256")
    methods = set(auth.split(","))
    safe_auth = methods <= {"none", "password", "md5", "scram-sha-256"}
    if all(method.startswith("!") for method in methods):
        safe_auth = {"!gss", "!sspi", "!oauth"} <= methods
    if (
        not safe_auth
        or values.get("gssencmode") != "disable"
        or values.get("gssdelegation", "0") != "0"
        or any(values.get(k) for k in values if k.startswith("oauth_") or k == "sslkeylogfile")
    ):
        raise ValueError("external authentication is unsupported")
    values["require_auth"] = auth
    values.setdefault("dbname", values["user"])
    if values.get("sslrootcert") == "system" and "sslmode" not in explicit and "PGSSLMODE" not in env:
        values["sslmode"] = "verify-full"
    if not host.startswith("/") and values.get("sslmode") != "disable":
        if values.get("sslcertmode") != "disable" and not values.get("sslpassword"):
            raise ValueError("TLS key prompting is unsupported")
    for key in ("passfile", "sslcert", "sslkey", "sslrootcert", "sslcrl", "sslcrldir"):
        value = values.get(key)
        if value and not (key == "sslrootcert" and value == "system"):
            if "://" in value or (key == "sslkey" and ":" in value):
                raise ValueError("external configuration facility")
            values[key] = str(Path(value).absolute())
    if values.get("requirepeer") or (values.get("sslrootcert") == "system" and any(
        env.get(k) for k in ("SSL_CERT_FILE", "SSL_CERT_DIR")
    )):
        raise ValueError("external identity or TLS defaults")
    home = env.get("HOME", "")
    if not home.startswith("/"):
        raise ValueError("home directory must not require an account lookup")
    defaults = {"passfile": ".pgpass", "sslcert": ".postgresql/postgresql.crt",
                "sslkey": ".postgresql/postgresql.key", "sslrootcert": ".postgresql/root.crt"}
    if not values.get("sslcrldir"):
        defaults["sslcrl"] = ".postgresql/root.crl"
    for key, relative in defaults.items():
        if not values.get(key):
            values[key] = str(Path(home) / relative)
    return values


def prepare_signing_conninfo(dsn: str) -> bytes:
    try:
        return make_conninfo(**dict(sorted(_prepared_options(dsn).items()))).encode()
    except (psycopg.Error, TypeError, ValueError, AttributeError):
        pass
    raise SigningObservationConfigError("unsupported signing observation configuration")


class _BoundedConnection(psycopg.Connection):
    def wait(self, gen, interval=0.1):
        return wait(gen, lambda: self.pgconn.socket, self._deadline, self._cancel_event)


def _connect_existing(pgconn):
    while True:
        state = pgconn.connect_poll()
        if state == pq.PollingStatus.OK:
            pgconn.nonblocking = 1
            return
        if state not in (pq.PollingStatus.READING, pq.PollingStatus.WRITING):
            raise psycopg.OperationalError("signing connection failed")
        requested = Wait.R if state == pq.PollingStatus.READING else Wait.W
        while not (yield requested):
            pass


class ObservationConnectionOwner:
    """Caller-owned slots remain live across acquisition and helper return."""

    def __init__(self):
        self.pgconn = None
        self.connection = None

    def close(self):
        if self.connection is not None:
            self.connection.close()
        elif self.pgconn is not None:
            self.pgconn.finish()


def connect_observation(conninfo: bytes, deadline: float, cancel_event, *, owner):
    """Borrow through the caller's active owner; never transfer cleanup."""
    checkpoint(deadline, cancel_event)
    if prepare_signing_conninfo(conninfo.decode()) != conninfo:
        raise SigningObservationConfigError("signing observation environment changed")
    checkpoint(deadline, cancel_event)
    owner.pgconn = pq.PGconn.connect_start(conninfo)
    wait(_connect_existing(owner.pgconn), lambda: owner.pgconn.socket, deadline, cancel_event)
    owner.connection = _BoundedConnection(owner.pgconn)
    connection = owner.connection
    connection._deadline = deadline
    connection._cancel_event = cancel_event
    connection.autocommit = True
    connection.prepare_threshold = None
    checkpoint(deadline, cancel_event)
    return connection


def read_signing_receipt(path: Path, *, deadline: float, cancel_event=None) -> bytes:
    checkpoint(deadline, cancel_event)
    descriptor = None
    with disposing(lambda: os.close(descriptor) if descriptor is not None else None):
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        checkpoint(deadline, cancel_event)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("signing receipt is not a regular file")
        checkpoint(deadline, cancel_event)
        receipt = b""
        while len(receipt) <= SIGNING_EVIDENCE_MAX_BYTES:
            checkpoint(deadline, cancel_event)
            chunk = os.read(descriptor, SIGNING_EVIDENCE_MAX_BYTES + 1 - len(receipt))
            checkpoint(deadline, cancel_event)
            if not chunk:
                break
            receipt += chunk
        if not 1 <= len(receipt) <= SIGNING_EVIDENCE_MAX_BYTES:
            raise OSError("signing evidence receipt size differs")
        return receipt
