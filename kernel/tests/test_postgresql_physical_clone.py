"""Live hostile evidence for the V1 physical-restore boundary.

This test deliberately proves the limit of issue #174's result.  A physical
standby copied from a fully migrated tenant cluster retains the source system
identifier and migration ledger.  Promotion makes ``pg_is_in_recovery()``
false, but the only result issue #174 may return is structural compatibility.
"""

from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import time
from dataclasses import fields
from pathlib import Path
from uuid import uuid4

import psycopg
import psycopg.conninfo
import pytest

from deployment.postgresql.migration_runner import migrate_service
from deployment.postgresql.migration_sets import (
    TENANT_SERVICE,
    load_authoritative_migration_set,
)
from deployment.postgresql.provisioning import provision_service
from deployment.postgresql.provisioning_specs import TENANT_PROVISIONING_SPEC
from deployment.postgresql.readiness import (
    PostgreSQLStructuralCompatibilityReport,
    verify_tenant_structural_compatibility,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
POSTGRES_IMAGE = (
    "postgres@sha256:"
    "5f050f770b427fbd477edee6c3968a72e5c6be97e050a7e368b2b74a9494a285"
)
POSTGRES_PORT = "5432/tcp"
POSTGRES_SUPERUSER = "ofarm"
POSTGRES_SUPERUSER_PASSWORD = "issue-174-physical-clone-test"
DOCKER_COMMAND_TIMEOUT_SECONDS = 60
POSTGRES_START_TIMEOUT_SECONDS = 30
_FORBIDDEN_RESULT_FIELDS = (
    "continuity",
    "promotion",
    "ready",
    "recovery",
    "runtime",
)


def _docker(
    *arguments: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("docker", *arguments),
        check=check,
        capture_output=True,
        text=True,
        timeout=DOCKER_COMMAND_TIMEOUT_SECONDS,
    )


def _require_exact_pinned_image() -> None:
    if shutil.which("docker") is None:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            pytest.fail("the GitHub runner has no Docker client")
        pytest.skip("Docker is required for the physical-clone hostile test")

    daemon = _docker("info", "--format", "{{.ServerVersion}}", check=False)
    if daemon.returncode != 0:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            pytest.fail("the GitHub runner Docker daemon is unavailable")
        pytest.skip("a Docker daemon is required for the physical-clone test")

    image = _docker("image", "inspect", POSTGRES_IMAGE, check=False)
    if image.returncode != 0:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            pytest.fail("the exact pinned PostgreSQL image is unavailable")
        pytest.skip("the exact pinned PostgreSQL image is not present locally")


def _remove_container(name: str) -> None:
    _docker("container", "rm", "--force", "--volumes", name, check=False)


def _published_port(container_name: str) -> int:
    output = _docker("port", container_name, POSTGRES_PORT).stdout.strip()
    host, separator, port = output.rpartition(":")
    if separator != ":" or host != "127.0.0.1" or not port.isdigit():
        raise AssertionError(f"unexpected published PostgreSQL port: {output!r}")
    return int(port)


def _dsn(port: int, database_name: str, user: str, password: str) -> str:
    return psycopg.conninfo.make_conninfo(
        host="127.0.0.1",
        port=port,
        dbname=database_name,
        user=user,
        password=password,
    )


def _wait_for_postgres(
    admin_dsn: str,
    *,
    expected_recovery: bool,
) -> None:
    deadline = time.monotonic() + POSTGRES_START_TIMEOUT_SECONDS
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(
                admin_dsn,
                autocommit=True,
                connect_timeout=1,
            ) as connection:
                row = connection.execute(
                    "SELECT pg_catalog.pg_is_in_recovery()"
                ).fetchone()
            if row == (expected_recovery,):
                return
        except psycopg.Error as exc:
            last_error = exc
        time.sleep(0.2)
    raise AssertionError(
        "PostgreSQL did not reach the expected recovery state"
    ) from last_error


def _system_identifier(admin_dsn: str) -> str:
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        row = connection.execute(
            "SELECT system_identifier::text "
            "FROM pg_catalog.pg_control_system()"
        ).fetchone()
    assert row is not None
    assert isinstance(row[0], str)
    return row[0]


def _migration_ledger(admin_dsn: str) -> list[tuple[object, ...]]:
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        return connection.execute(
            """
            SELECT version,
                   filename,
                   source_sha256,
                   source_byte_length,
                   applied_prefix_digest,
                   service_identity,
                   provisioning_spec_digest,
                   release_identity,
                   execution_id::text,
                   applied_at
            FROM ofarm.schema_migration
            ORDER BY version
            """
        ).fetchall()


def _assert_structural_only_result(
    report: PostgreSQLStructuralCompatibilityReport,
) -> None:
    assert tuple(field.name for field in fields(report)) == (
        "service_identity",
        "supported_version",
        "observed_version",
    )
    manifest = report.manifest()
    assert set(manifest) == {
        "schemaVersion",
        "serviceIdentity",
        "supportedVersion",
        "observedVersion",
    }
    assert manifest["schemaVersion"] == (
        "ofarm.postgresql-structural-compatibility.v1"
    )
    normalized_field_names = {
        field_name.lower().replace("_", "")
        for field_name in (
            *(field.name for field in fields(report)),
            *manifest,
        )
    }
    for forbidden in _FORBIDDEN_RESULT_FIELDS:
        assert all(forbidden not in name for name in normalized_field_names)
        assert not hasattr(report, forbidden)


def test_promoted_physical_clone_yields_only_structural_compatibility():
    """Promotion cannot turn issue #174 evidence into continuity proof."""

    _require_exact_pinned_image()
    nonce = uuid4().hex
    network_name = f"ofarm174-network-{nonce}"
    source_name = f"ofarm174-source-{nonce}"
    clone_name = f"ofarm174-clone-{nonce}"
    helper_name = f"ofarm174-basebackup-{nonce}"
    clone_volume = f"ofarm174-clone-data-{nonce}"

    try:
        _docker("network", "create", network_name)
        _docker("volume", "create", clone_volume)
        _docker(
            "run",
            "--detach",
            "--name",
            source_name,
            "--network",
            network_name,
            "--publish",
            "127.0.0.1::5432",
            "--env",
            f"POSTGRES_USER={POSTGRES_SUPERUSER}",
            "--env",
            f"POSTGRES_PASSWORD={POSTGRES_SUPERUSER_PASSWORD}",
            "--env",
            "POSTGRES_DB=postgres",
            POSTGRES_IMAGE,
        )
        source_port = _published_port(source_name)
        source_admin_dsn = _dsn(
            source_port,
            "postgres",
            POSTGRES_SUPERUSER,
            POSTGRES_SUPERUSER_PASSWORD,
        )
        _wait_for_postgres(source_admin_dsn, expected_recovery=False)

        tenant_passwords = {
            role_name: (
                f"physical-clone-{index}-{secrets.token_urlsafe(32)}"
            )
            for index, role_name in enumerate(
                TENANT_PROVISIONING_SPEC.required_password_role_names
            )
        }
        provision_service(
            source_admin_dsn,
            TENANT_PROVISIONING_SPEC,
            login_passwords=tenant_passwords,
        )
        migrate_service(
            admin_dsn=source_admin_dsn,
            migrator_dsn=_dsn(
                source_port,
                TENANT_PROVISIONING_SPEC.database_name,
                "ofarm_migrator",
                tenant_passwords["ofarm_migrator"],
            ),
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=load_authoritative_migration_set(
                PACKAGE_ROOT,
                TENANT_SERVICE,
            ),
            release_identity="issue-174-physical-clone-hostile-test",
            execution_id=uuid4(),
        )
        source_target_dsn = _dsn(
            source_port,
            TENANT_PROVISIONING_SPEC.database_name,
            POSTGRES_SUPERUSER,
            POSTGRES_SUPERUSER_PASSWORD,
        )
        source_identifier = _system_identifier(source_admin_dsn)
        source_ledger = _migration_ledger(source_target_dsn)
        assert source_ledger

        _docker(
            "run",
            "--rm",
            "--name",
            helper_name,
            "--network",
            f"container:{source_name}",
            "--env",
            f"PGPASSWORD={POSTGRES_SUPERUSER_PASSWORD}",
            "--volume",
            f"{clone_volume}:/var/lib/postgresql/data",
            "--entrypoint",
            "/bin/sh",
            POSTGRES_IMAGE,
            "-ec",
            "chown postgres:postgres /var/lib/postgresql/data && "
            "exec gosu postgres pg_basebackup "
            "--host=127.0.0.1 --port=5432 "
            f"--username={POSTGRES_SUPERUSER} "
            "--pgdata=/var/lib/postgresql/data "
            "--checkpoint=fast --wal-method=stream "
            "--write-recovery-conf --no-password",
        )

        _docker(
            "run",
            "--detach",
            "--name",
            clone_name,
            "--network",
            network_name,
            "--publish",
            "127.0.0.1::5432",
            "--volume",
            f"{clone_volume}:/var/lib/postgresql/data",
            POSTGRES_IMAGE,
        )
        clone_port = _published_port(clone_name)
        clone_admin_dsn = _dsn(
            clone_port,
            "postgres",
            POSTGRES_SUPERUSER,
            POSTGRES_SUPERUSER_PASSWORD,
        )
        _wait_for_postgres(clone_admin_dsn, expected_recovery=True)

        with psycopg.connect(clone_admin_dsn, autocommit=True) as clone_admin:
            promoted = clone_admin.execute(
                "SELECT pg_catalog.pg_promote(true, 30)"
            ).fetchone()
        assert promoted == (True,)
        _wait_for_postgres(clone_admin_dsn, expected_recovery=False)

        clone_target_dsn = _dsn(
            clone_port,
            TENANT_PROVISIONING_SPEC.database_name,
            POSTGRES_SUPERUSER,
            POSTGRES_SUPERUSER_PASSWORD,
        )
        assert _system_identifier(clone_admin_dsn) == source_identifier
        assert _migration_ledger(clone_target_dsn) == source_ledger

        report = verify_tenant_structural_compatibility(
            tenant_structural_dsn=_dsn(
                clone_port,
                TENANT_PROVISIONING_SPEC.database_name,
                "ofarm_readiness",
                tenant_passwords["ofarm_readiness"],
            )
        )
        assert report.service_identity == TENANT_SERVICE.identity
        _assert_structural_only_result(report)
    finally:
        _remove_container(helper_name)
        _remove_container(clone_name)
        _remove_container(source_name)
        _docker("volume", "rm", "--force", clone_volume, check=False)
        _docker("network", "rm", network_name, check=False)
