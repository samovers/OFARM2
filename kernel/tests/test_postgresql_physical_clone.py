"""Live hostile evidence for V1 physical-restore and postmaster boundaries.

This test deliberately proves the limit of issue #174's result.  A physical
standby copied from a fully migrated tenant cluster retains the source system
identifier and migration ledger.  Promotion makes ``pg_is_in_recovery()``
false, but the only result issue #174 may return is structural compatibility.
The same disposable-container harness also proves that both structural lanes
refuse PostgreSQL with prepared-transaction capacity enabled.
"""

from __future__ import annotations

import os
import json
import re
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
    SECURITY_AUDIT_SERVICE,
    TENANT_SERVICE,
    load_authoritative_migration_set,
)
from deployment.postgresql.provisioning import provision_service
from deployment.postgresql.provisioning_specs import (
    SECURITY_AUDIT_PROVISIONING_SPEC,
    TENANT_PROVISIONING_SPEC,
)
from deployment.postgresql.readiness import (
    PostgreSQLStructuralCompatibilityReport,
    PostgreSQLVerificationError,
    verify_security_audit_structural_compatibility,
    verify_tenant_structural_compatibility,
)
from deployment.postgresql.native_evidence import docker_transport_child_identity


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DERIVED_IMAGE_ENV = "ISSUE174_DERIVED_POSTGRES_IMAGE"
DERIVED_ARCHIVE_ENV = "ISSUE174_DERIVED_POSTGRES_ARCHIVE"
DERIVED_CHILD_DIGEST_ENV = "ISSUE174_DERIVED_POSTGRES_CHILD_DIGEST"
DERIVED_CONFIG_DIGEST_ENV = "ISSUE174_DERIVED_POSTGRES_CONFIG_DIGEST"
DERIVED_IDENTITY_STATUS_ENV = "ISSUE174_DERIVED_POSTGRES_IDENTITY_STATUS"
EXPECTED_DERIVED_IMAGE = "ofarm-postgresql-conformance:local"
SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
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


def _required_environment(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    if os.environ.get("GITHUB_ACTIONS") == "true":
        pytest.fail(f"the GitHub runner is missing required {name}")
    return None


def _require_exact_pinned_image() -> str:
    image_name = _required_environment(DERIVED_IMAGE_ENV)
    archive_name = _required_environment(DERIVED_ARCHIVE_ENV)
    expected_child = _required_environment(DERIVED_CHILD_DIGEST_ENV)
    expected_config = _required_environment(DERIVED_CONFIG_DIGEST_ENV)
    identity_status = _required_environment(DERIVED_IDENTITY_STATUS_ENV)
    if None in (
        image_name,
        archive_name,
        expected_child,
        expected_config,
        identity_status,
    ):
        pytest.skip("the locally built derived PostgreSQL image is not configured")
    assert image_name is not None
    assert archive_name is not None
    assert expected_child is not None
    assert expected_config is not None
    assert identity_status is not None
    if identity_status != "frozen":
        pytest.fail("the derived PostgreSQL release identity is not frozen")
    if image_name != EXPECTED_DERIVED_IMAGE:
        pytest.fail("the physical-clone image name is not the CI-local derived tag")
    if (
        SHA256_PATTERN.fullmatch(expected_child) is None
        or SHA256_PATTERN.fullmatch(expected_config) is None
    ):
        pytest.fail("the frozen derived PostgreSQL identity is malformed")

    if shutil.which("docker") is None:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            pytest.fail("the GitHub runner has no Docker client")
        pytest.skip("Docker is required for the physical-clone hostile test")

    daemon = _docker("info", "--format", "{{.ServerVersion}}", check=False)
    if daemon.returncode != 0:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            pytest.fail("the GitHub runner Docker daemon is unavailable")
        pytest.skip("a Docker daemon is required for the physical-clone test")

    archive_path = Path(archive_name)
    if not archive_path.is_absolute():
        archive_path = PACKAGE_ROOT / archive_path
    observed_child, observed_config = docker_transport_child_identity(
        archive_path,
        "derived PostgreSQL Docker transport archive",
        platform="linux/amd64",
        image_name=EXPECTED_DERIVED_IMAGE,
    )
    if (observed_child, observed_config) != (expected_child, expected_config):
        pytest.fail(
            "the derived PostgreSQL Docker transport differs from frozen identity"
        )

    image = _docker("image", "inspect", image_name, check=False)
    if image.returncode != 0:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            pytest.fail("the exact pinned PostgreSQL image is unavailable")
        pytest.skip("the exact derived PostgreSQL image is not present locally")
    try:
        inspected_images = json.loads(image.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError("Docker returned malformed image inspection JSON") from exc
    if not isinstance(inspected_images, list) or len(inspected_images) != 1:
        pytest.fail("Docker did not return one exact derived image")
    inspected = inspected_images[0]
    if (
        not isinstance(inspected, dict)
        or inspected.get("Id") not in {expected_child, expected_config}
        or inspected.get("Architecture") != "amd64"
        or inspected.get("Os") != "linux"
        or image_name not in inspected.get("RepoTags", [])
    ):
        pytest.fail("the loaded derived PostgreSQL image differs from frozen identity")
    return image_name


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


def _enable_prepared_transactions(
    container_name: str,
    admin_dsn: str,
) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        posture = connection.execute(
            "SELECT setting::integer, context::text "
            "FROM pg_catalog.pg_settings "
            "WHERE name = 'max_prepared_transactions'"
        ).fetchone()
        assert posture == (0, "postmaster")
        connection.execute(
            "ALTER SYSTEM SET max_prepared_transactions = '1'"
        )

    _docker("restart", container_name)
    _wait_for_postgres(admin_dsn, expected_recovery=False)

    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        posture = connection.execute(
            "SELECT setting::integer, context::text "
            "FROM pg_catalog.pg_settings "
            "WHERE name = 'max_prepared_transactions'"
        ).fetchone()
    assert posture == (1, "postmaster")


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

    postgres_image = _require_exact_pinned_image()
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
            postgres_image,
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
            postgres_image,
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
            postgres_image,
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

        tenant_readiness_dsn = _dsn(
            clone_port,
            TENANT_PROVISIONING_SPEC.database_name,
            "ofarm_readiness",
            tenant_passwords["ofarm_readiness"],
        )
        report = verify_tenant_structural_compatibility(
            tenant_structural_dsn=tenant_readiness_dsn,
        )
        assert report.service_identity == TENANT_SERVICE.identity
        _assert_structural_only_result(report)

        _enable_prepared_transactions(clone_name, clone_admin_dsn)
        with psycopg.connect(
            tenant_readiness_dsn,
            autocommit=True,
        ) as readiness:
            structural = readiness.execute(
                "SELECT structurally_compatible, difference_count "
                "FROM ofarm.verify_tenant_structure()"
            ).fetchone()
        assert structural == (False, 1)
        with pytest.raises(
            PostgreSQLVerificationError,
            match="tenant contract observation differs",
        ):
            verify_tenant_structural_compatibility(
                tenant_structural_dsn=tenant_readiness_dsn,
            )
    finally:
        _remove_container(helper_name)
        _remove_container(clone_name)
        _remove_container(source_name)
        _docker("volume", "rm", "--force", clone_volume, check=False)
        _docker("network", "rm", network_name, check=False)


def test_security_audit_observer_refuses_prepared_transaction_capacity():
    """Audit structural compatibility refuses a nonzero postmaster setting."""

    postgres_image = _require_exact_pinned_image()
    nonce = uuid4().hex
    container_name = f"ofarm174-audit-posture-{nonce}"

    try:
        _docker(
            "run",
            "--detach",
            "--name",
            container_name,
            "--publish",
            "127.0.0.1::5432",
            "--env",
            f"POSTGRES_USER={POSTGRES_SUPERUSER}",
            "--env",
            f"POSTGRES_PASSWORD={POSTGRES_SUPERUSER_PASSWORD}",
            "--env",
            "POSTGRES_DB=postgres",
            postgres_image,
        )
        audit_port = _published_port(container_name)
        audit_admin_dsn = _dsn(
            audit_port,
            "postgres",
            POSTGRES_SUPERUSER,
            POSTGRES_SUPERUSER_PASSWORD,
        )
        _wait_for_postgres(audit_admin_dsn, expected_recovery=False)

        audit_passwords = {
            role_name: f"audit-posture-{index}-{secrets.token_urlsafe(32)}"
            for index, role_name in enumerate(
                SECURITY_AUDIT_PROVISIONING_SPEC.required_password_role_names
            )
        }
        provision_service(
            audit_admin_dsn,
            SECURITY_AUDIT_PROVISIONING_SPEC,
            login_passwords=audit_passwords,
        )
        migrate_service(
            admin_dsn=audit_admin_dsn,
            migrator_dsn=_dsn(
                audit_port,
                SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
                "ofarm_migrator",
                audit_passwords["ofarm_migrator"],
            ),
            spec=SECURITY_AUDIT_PROVISIONING_SPEC,
            migration_set=load_authoritative_migration_set(
                PACKAGE_ROOT,
                SECURITY_AUDIT_SERVICE,
            ),
            release_identity="issue-174-audit-postmaster-hostile-test",
            execution_id=uuid4(),
        )
        audit_readiness_dsn = _dsn(
            audit_port,
            SECURITY_AUDIT_PROVISIONING_SPEC.database_name,
            "ofarm_security_audit_readiness_login",
            audit_passwords["ofarm_security_audit_readiness_login"],
        )
        report = verify_security_audit_structural_compatibility(
            audit_structural_dsn=audit_readiness_dsn,
        )
        assert report.service_identity == SECURITY_AUDIT_SERVICE.identity
        _assert_structural_only_result(report)

        _enable_prepared_transactions(container_name, audit_admin_dsn)
        with psycopg.connect(
            audit_readiness_dsn,
            autocommit=True,
        ) as readiness:
            structural = readiness.execute(
                "SELECT * FROM "
                "ofarm_security.verify_security_audit_structure()"
            ).fetchone()
        assert structural == (False, 1, False)
        with pytest.raises(
            PostgreSQLVerificationError,
            match="security-audit contract observation differs",
        ):
            verify_security_audit_structural_compatibility(
                audit_structural_dsn=audit_readiness_dsn,
            )
    finally:
        _remove_container(container_name)
