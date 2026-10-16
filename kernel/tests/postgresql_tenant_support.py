"""Fresh tenant service custody and current-state runtime test support."""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest

from deployment.postgresql.migration_runner import migrate_service
from deployment.postgresql.migration_sets import (
    TENANT_SERVICE,
    MigrationSet,
    load_migration_set,
)
from deployment.postgresql.provisioning import provision_service
from deployment.postgresql.provisioning_specs import TENANT_PROVISIONING_SPEC
from kernel.tests.test_postgresql_migration_runner import (
    _assert_clean_service,
    _database_dsn,
    _destroy_test_service,
    _passwords,
)

ADMIN_ENV = "OFARM_TENANT_PROVISIONING_PG_ADMIN_DSN"
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
RELEASE_IDENTITY = "ofarm-tests/tenant-runtime-fixture"


@dataclass(frozen=True, slots=True)
class TenantTarget:
    """Operational facts only; staged migration evidence belongs to its owner."""

    admin_dsn: str
    target_admin_dsn: str
    migrator_dsn: str
    passwords: Mapping[str, str]
    migration_set: MigrationSet

    def role_dsn(self, role_name: str) -> str:
        return _database_dsn(
            self.admin_dsn,
            TENANT_PROVISIONING_SPEC.database_name,
            user=role_name,
            password=self.passwords[role_name],
        )


@contextmanager
def fresh_tenant_service(admin_dsn: str) -> Iterator[TenantTarget]:
    """Refuse dirty routes before ownership; dispose every owned setup outcome."""

    spec = TENANT_PROVISIONING_SPEC
    _assert_clean_service(admin_dsn, spec)
    passwords = _passwords(spec, "tenant-baseline")
    migration_set = load_migration_set(PACKAGE_ROOT, TENANT_SERVICE)
    try:
        provision_service(admin_dsn, spec, login_passwords=passwords)
        yield TenantTarget(
            admin_dsn=admin_dsn,
            target_admin_dsn=_database_dsn(admin_dsn, spec.database_name),
            migrator_dsn=_database_dsn(
                admin_dsn,
                spec.database_name,
                user="ofarm_migrator",
                password=passwords["ofarm_migrator"],
            ),
            passwords=passwords,
            migration_set=migration_set,
        )
    finally:
        _destroy_test_service(admin_dsn, spec)


@pytest.fixture(scope="module")
def tenant_target() -> Iterator[TenantTarget]:
    """Build a fresh current schema through the full public migration path."""

    admin_dsn = os.environ.get(ADMIN_ENV)
    if not admin_dsn:
        pytest.skip(f"{ADMIN_ENV} is required for real PostgreSQL tests")
    with fresh_tenant_service(admin_dsn) as target:
        first_report = migrate_service(
            admin_dsn=target.admin_dsn,
            migrator_dsn=target.migrator_dsn,
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=target.migration_set,
            release_identity=RELEASE_IDENTITY,
            execution_id=uuid4(),
        )
        assert first_report.previous_version == 0
        assert first_report.applied_versions == tuple(range(1, 12))
        assert first_report.final_version == 11
        assert first_report.observed_head_execution_id == first_report.execution_id
        noop_report = migrate_service(
            admin_dsn=target.admin_dsn,
            migrator_dsn=target.migrator_dsn,
            spec=TENANT_PROVISIONING_SPEC,
            migration_set=target.migration_set,
            release_identity=RELEASE_IDENTITY,
            execution_id=uuid4(),
        )
        assert noop_report.previous_version == noop_report.final_version == 11
        assert noop_report.applied_versions == ()
        assert noop_report.verified_noop
        assert noop_report.observed_head_execution_id == first_report.execution_id
        assert noop_report.execution_id != first_report.execution_id
        yield target
