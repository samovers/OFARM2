"""Closed command-line lane tests for issue #174 migrations."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

import deployment.postgresql.migration_cli as migration_cli
import deployment.postgresql.migration_runner as migration_runner
import deployment.postgresql.run_security_audit_migrations as audit_cli
import deployment.postgresql.run_tenant_migrations as tenant_cli
from deployment.postgresql.migration_runner import MigrationRunReport
from deployment.postgresql.migration_runner import MigrationTargetError
from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_SERVICE,
    TENANT_SERVICE,
    load_migration_set,
)
from deployment.postgresql.provisioning_specs import (
    SECURITY_AUDIT_PROVISIONING_SPEC,
    TENANT_PROVISIONING_SPEC,
)
from deployment.postgresql.version_policy import (
    SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
)


_EXECUTION_ID = UUID("11111111-1111-4111-8111-111111111111")


def _write_set(root: Path, relative_directory: str) -> None:
    directory = root / relative_directory
    directory.mkdir(parents=True)
    (directory / "0001_initial.sql").write_bytes(b"SELECT 1;\n")


@pytest.mark.parametrize(
    (
        "module",
        "service",
        "spec",
        "admin_environment",
        "migrator_environment",
    ),
    (
        (
            tenant_cli,
            TENANT_SERVICE,
            TENANT_PROVISIONING_SPEC,
            "OFARM_TENANT_PROVISIONING_PG_ADMIN_DSN",
            "OFARM_TENANT_MIGRATOR_DSN",
        ),
        (
            audit_cli,
            SECURITY_AUDIT_SERVICE,
            SECURITY_AUDIT_PROVISIONING_SPEC,
            "OFARM_SECURITY_AUDIT_PG_ADMIN_DSN",
            "OFARM_SECURITY_AUDIT_MIGRATOR_DSN",
        ),
    ),
)
def test_each_entry_point_has_one_fixed_service_and_route_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    module,
    service,
    spec,
    admin_environment: str,
    migrator_environment: str,
):
    _write_set(tmp_path, service.relative_directory)
    monkeypatch.setattr(migration_cli, "_PACKAGE_ROOT", tmp_path)
    monkeypatch.setattr(
        migration_cli,
        "load_authoritative_migration_set",
        load_migration_set,
    )
    monkeypatch.setenv(admin_environment, "admin-route")
    monkeypatch.setenv(migrator_environment, "migrator-route")
    observed: dict[str, object] = {}

    def fake_migrate_service(**values):
        observed.update(values)
        migration_set = values["migration_set"]
        return MigrationRunReport(
            service_identity=service.identity,
            provisioning_spec_digest=spec.digest,
            migration_set_digest=migration_set.digest,
            database_name=spec.database_name,
            system_identifier="123",
            server_version_num=SUPPORTED_POSTGRESQL_SERVER_VERSION_NUM,
            previous_version=0,
            final_version=1,
            applied_versions=(1,),
            execution_id=_EXECUTION_ID,
            observed_head_execution_id=_EXECUTION_ID,
        )

    monkeypatch.setattr(migration_cli, "migrate_service", fake_migrate_service)

    assert module.main(
        [
            "--release-identity",
            "ofarm-release/174",
            "--execution-id",
            str(_EXECUTION_ID),
        ]
    ) == 0

    assert observed["admin_dsn"] == "admin-route"
    assert observed["migrator_dsn"] == "migrator-route"
    assert observed["spec"] is spec
    assert observed["migration_set"].service is service
    assert observed["release_identity"] == "ofarm-release/174"
    assert observed["execution_id"] == _EXECUTION_ID
    output = json.loads(capsys.readouterr().out)
    assert output["serviceIdentity"] == service.identity
    assert output["executionId"] == str(_EXECUTION_ID)
    assert output["observedHeadExecutionId"] == str(_EXECUTION_ID)


def test_missing_fixed_route_refuses_before_loading_migrations(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv(
        "OFARM_TENANT_PROVISIONING_PG_ADMIN_DSN",
        raising=False,
    )
    monkeypatch.delenv("OFARM_TENANT_MIGRATOR_DSN", raising=False)

    with pytest.raises(SystemExit) as raised:
        tenant_cli.main(
            [
                "--release-identity",
                "ofarm-release/174",
                "--execution-id",
                str(_EXECUTION_ID),
            ]
        )

    assert raised.value.code == 2


@pytest.mark.parametrize(
    "execution_id",
    (
        "00000000-0000-0000-0000-000000000000",
        "11111111-1111-4111-8111-11111111111A",
        "not-a-uuid",
    ),
)
def test_execution_identity_is_canonical_and_non_nil(
    execution_id: str,
):
    with pytest.raises(SystemExit) as raised:
        tenant_cli.main(
            [
                "--release-identity",
                "ofarm-release/174",
                "--execution-id",
                execution_id,
            ]
        )

    assert raised.value.code == 2


def test_admin_connection_error_is_sanitized_at_the_cli_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_set(tmp_path, SECURITY_AUDIT_SERVICE.relative_directory)
    monkeypatch.setattr(migration_cli, "_PACKAGE_ROOT", tmp_path)
    monkeypatch.setattr(
        migration_cli,
        "load_authoritative_migration_set",
        load_migration_set,
    )
    monkeypatch.setattr(
        migration_cli,
        "migrate_service",
        migration_runner._migrate_service_for_testing,
    )
    monkeypatch.setenv(
        "OFARM_SECURITY_AUDIT_PG_ADMIN_DSN",
        "host=admin-route.invalid dbname=postgres",
    )
    monkeypatch.setenv(
        "OFARM_SECURITY_AUDIT_MIGRATOR_DSN",
        "host=migrator-route.invalid dbname=ofarm_security",
    )

    def refuse_admin_route(*_args, **_kwargs):
        raise psycopg.OperationalError("SECRET-ADMIN-ROUTE-SENTINEL")

    monkeypatch.setattr(
        migration_runner,
        "verify_service_infrastructure",
        refuse_admin_route,
    )

    with pytest.raises(SystemExit) as raised:
        audit_cli.main(
            [
                "--release-identity",
                "ofarm-release/174",
                "--execution-id",
                str(_EXECUTION_ID),
            ]
        )

    captured = capsys.readouterr()
    assert raised.value.code == 1
    assert captured.out == ""
    assert captured.err == (
        "migration refused: admin provisioning route is unavailable\n"
    )
    assert "SECRET-ADMIN-ROUTE-SENTINEL" not in captured.out + captured.err


@pytest.mark.parametrize("failure_stage", ("BEGIN", "SET LOCAL"))
def test_transaction_setup_failure_is_sanitized_at_the_cli_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure_stage: str,
) -> None:
    _write_set(tmp_path, TENANT_SERVICE.relative_directory)
    monkeypatch.setattr(migration_cli, "_PACKAGE_ROOT", tmp_path)
    monkeypatch.setattr(
        migration_cli,
        "load_authoritative_migration_set",
        load_migration_set,
    )
    monkeypatch.setenv(
        "OFARM_TENANT_PROVISIONING_PG_ADMIN_DSN", "admin-route"
    )
    monkeypatch.setenv("OFARM_TENANT_MIGRATOR_DSN", "migrator-route")

    def refuse_transaction_setup(**_values):
        try:
            raise psycopg.OperationalError(
                f"SECRET-{failure_stage}-TRANSACTION-SENTINEL"
            )
        except psycopg.OperationalError as exc:
            raise MigrationTargetError(
                "protected migration transaction setup failed"
            ) from exc

    monkeypatch.setattr(
        migration_cli, "migrate_service", refuse_transaction_setup
    )

    with pytest.raises(SystemExit) as raised:
        tenant_cli.main(
            [
                "--release-identity",
                "ofarm-release/174",
                "--execution-id",
                str(_EXECUTION_ID),
            ]
        )

    captured = capsys.readouterr()
    assert raised.value.code == 1
    assert captured.out == ""
    assert captured.err == (
        "migration refused: protected migration transaction setup failed\n"
    )
    assert "SECRET" not in captured.err
    assert "Traceback" not in captured.err
