"""Owned disposable PostgreSQL controls for real physical-outcome crash tests.

No control discovers or kills an ambient server: the container name is created
here, and every destructive command first verifies its unpredictable owner label.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import socket
from uuid import uuid4

import psycopg
import pytest

from kernel.tests import test_postgresql_tenant_migration as migration
from kernel.tests.test_postgresql_physical_clone import (
    _docker, _dsn, _published_port, _require_exact_pinned_image,
    _wait_for_postgres,
)


@dataclass
class CrashCluster:
    name: str
    owner: str
    admin_dsn: str
    system_identifier: str
    paused_writer: int | None = None

    def admin(self):
        return psycopg.connect(self.admin_dsn, autocommit=True)

    def command(self, *arguments):
        observed = _docker(
            "inspect", "--format", '{{ index .Config.Labels "ofarm.physical-test" }}',
            self.name,
        ).stdout.strip()
        assert observed == self.owner, "crash fixture ownership differs"
        return _docker(*arguments)

    def signal(self, pid: int, signal: str):
        assert type(pid) is int and pid > 1
        assert signal in {"STOP", "CONT", "KILL"}
        self.command(
            "exec", "--user", "postgres", self.name,
            "sh", "-c", 'kill -"$1" "$2"', "physical-crash", signal, str(pid),
        )

    def checkpoint(self, *, pause_writer: bool = False):
        with self.admin() as admin:
            admin.execute("CHECKPOINT")
            settings = admin.execute(
                "SELECT current_setting('fsync'), current_setting('wal_writer_delay'), "
                "current_setting('checkpoint_timeout'), current_setting('autovacuum')"
            ).fetchone()
            assert settings == ("on", "10s", "1h", "off")
            if pause_writer:
                pid = admin.execute(
                    "SELECT pid FROM pg_stat_activity WHERE backend_type = 'walwriter'"
                ).fetchone()[0]
                self.signal(pid, "STOP")
                self.paused_writer = pid
        return self.positions()

    def positions(self):
        with self.admin() as admin:
            row = admin.execute(
                "SELECT pg_current_wal_insert_lsn()::text, "
                "pg_current_wal_flush_lsn()::text"
            ).fetchone()
        return {"insert": row[0], "flush": row[1]}

    def crash(self, *, restart: bool = False):
        with self.admin() as victim:
            before = victim.execute("SELECT pg_postmaster_start_time()").fetchone()[0]
            victim_pid = victim.info.backend_pid
            if restart:
                self.command("restart", self.name)
            else:
                if self.paused_writer is None:
                    self.signal(victim_pid, "KILL")
                else:
                    # A stopped writer cannot handle postmaster SIGQUIT. Kill it
                    # after the unrelated backend, without letting it flush WAL.
                    self.command(
                        "exec", "--user", "postgres", self.name, "sh", "-c",
                        'kill -KILL "$1"; kill -KILL "$2"', "physical-crash",
                        str(victim_pid), str(self.paused_writer),
                    )
                    self.paused_writer = None
        _wait_for_postgres(self.admin_dsn, expected_recovery=False)
        with self.admin() as admin:
            identifier, after = admin.execute(
                "SELECT system_identifier::text, pg_postmaster_start_time() "
                "FROM pg_control_system()"
            ).fetchone()
        assert identifier == self.system_identifier
        assert (after != before) if restart else (after == before)
        return {"system_identifier": identifier, "postmaster_restarted": restart,
                "postmaster_before": before.isoformat(), "postmaster_after": after.isoformat()}

    def flush_insert(self, insert_record_end: str):
        with psycopg.connect(self.admin_dsn) as admin:
            admin.execute("SET LOCAL synchronous_commit = 'on'")
            admin.execute("SELECT pg_current_xact_id()")
            admin.execute("SELECT pg_logical_emit_message(true, 'physical-test', 'flush')")
        flush = self.positions()["flush"]
        assert lsn(flush) >= lsn(insert_record_end)
        return flush


def lsn(value: str) -> int:
    high, low = value.split("/")
    return (int(high, 16) << 32) + int(low, 16)


@contextmanager
def crash_cluster():
    image = _require_exact_pinned_image()
    owner = uuid4().hex
    name = f"ofarm405-crash-{owner}"
    password = f"physical-fixture-{uuid4().hex}"
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    cluster = CrashCluster(name, owner, "", "")
    try:
        _docker(
            "run", "--detach", "--name", name,
            "--label", f"ofarm.physical-test={owner}",
            "--publish", f"127.0.0.1:{port}:5432",
            "--env", "POSTGRES_USER=ofarm", "--env", f"POSTGRES_PASSWORD={password}",
            "--env", "POSTGRES_DB=postgres", image,
            "-c", "wal_writer_delay=10s", "-c", "checkpoint_timeout=1h",
            "-c", "autovacuum=off",
        )

        admin_dsn = _dsn(_published_port(name), "postgres", "ofarm", password)
        _wait_for_postgres(admin_dsn, expected_recovery=False)
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            assert admin.info.server_version == 170010
            identifier = admin.execute(
                "SELECT system_identifier::text FROM pg_control_system()"
            ).fetchone()[0]
        cluster.admin_dsn = admin_dsn
        cluster.system_identifier = identifier
        yield cluster
    finally:
        exists = _docker("container", "inspect", name, check=False)
        if exists.returncode == 0:
            cluster.command("container", "rm", "--force", "--volumes", name)


@contextmanager
def crash_authority(cluster):
    """Reuse the existing complete provisioning and authority fixtures verbatim."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(migration, "_admin_dsn", lambda: cluster.admin_dsn)
        fixture = migration.tenant_target.__wrapped__()
        target = next(fixture)
        try:
            authority = migration.authority.__wrapped__(target)
            key = migration.capability_key.__wrapped__(target)
            yield target, authority, key
        finally:
            fixture.close()


def evidence(control, role, **facts):
    """Inspectable local stdout; no DSN, credentials or capabilities leave fixture."""
    print("PHYSICAL_CRASH_EVIDENCE " + json.dumps(
        {"control": control, "role": role, **facts}, sort_keys=True, default=str,
    ))
