"""Closed command-line lane tests for issue #174 migrations."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest

import deployment.postgresql.migration_cli as migration_cli
import deployment.postgresql.run_security_audit_migrations as audit_cli
import deployment.postgresql.run_tenant_migrations as tenant_cli
from deployment.postgresql.migration_runner import MigrationRunReport
from deployment.postgresql.migration_sets import (
    SECURITY_AUDIT_SERVICE,
    TENANT_SERVICE,
    load_migration_set,
)
from deployment.postgresql.provisioning_specs import (
    SECURITY_AUDIT_PROVISIONING_SPEC,
    TENANT_PROVISIONING_SPEC,
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
            server_version_num=170009,
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
