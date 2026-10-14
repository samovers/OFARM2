"""Signed receipts and disposal assertions for the real observation path."""
from __future__ import annotations

import os
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from kernel.signing_authority import SigningAuthority, SigningAuthorityReader
from kernel.signing_authority_io import prepare_signing_conninfo
from kernel.signing_receipt import SigningEvidenceVerifier
from kernel.tests._signing_support import (
    OBSERVER_PRIVATE_KEY, connected_test_dsn, raw_public_key, receipt_payload, signed_receipt,
)


def admitted_dsn(dsn: str, **changes) -> str:
    values = conninfo_to_dict(dsn)
    values.update(sslmode="disable", gssencmode="disable")
    values.update(changes)
    return make_conninfo(**values)


def observe(target, kid: str) -> tuple[SigningAuthority, str]:
    dsn = target.role_dsn("ofarm_app")
    with psycopg.connect(dsn, autocommit=True) as connection:
        dsn = connected_test_dsn(dsn, connection)
        assert connection.info.server_version == 170010
        assert connection.execute("SELECT SESSION_USER").fetchone() == ("ofarm_app",)
        row = connection.execute(
            "SELECT * FROM ofarm.observe_signing_authority(%s)", (kid,),
        ).fetchone()
    assert row is not None
    return SigningAuthority.from_database_row(row, kid), dsn


def write_receipt(path: Path, authority: SigningAuthority, **changes) -> bytes:
    payload = receipt_payload(
        authority,
        observedAtUnixMicroseconds=authority.observed_at_us,
        expiresAtUnixMicroseconds=authority.observed_at_us + 30_000_000,
    )
    payload.update(changes)
    raw = signed_receipt(payload)
    path.write_bytes(raw)
    return raw


def reader(dsn: str, path: Path) -> SigningAuthorityReader:
    return SigningAuthorityReader(
        prepare_signing_conninfo(dsn), path,
        SigningEvidenceVerifier(raw_public_key(OBSERVER_PRIVATE_KEY)),
    )


def assert_safe_refusal(error: BaseException) -> None:
    assert error.__context__ is None
    assert error.__cause__ is None
    assert "password" not in str(error).lower()
    assert "SELECT " not in str(error)


def retained_connections(monkeypatch):
    """Retain real wrappers before native close; no GC-based leak assertion."""
    import kernel.signing_authority_io as transport

    retained = []
    close = transport._BoundedConnection.close

    def record(connection):
        assert connection.pgconn.nonblocking == 1
        fd = connection.pgconn.socket
        retained.append((connection, fd))
        return close(connection)

    monkeypatch.setattr(transport._BoundedConnection, "close", record)
    return retained


def assert_disposed(retained) -> None:
    assert retained
    for connection, descriptor in retained:
        assert connection.closed
        assert connection.pgconn.status == psycopg.pq.ConnStatus.BAD
        # Retained wrappers/tracebacks cannot keep the original descriptor open.
        try:
            os.fstat(descriptor)
        except OSError:
            continue
        raise AssertionError("observation client descriptor remains open")
