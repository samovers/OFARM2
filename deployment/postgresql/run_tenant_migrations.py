"""Dedicated release entry point for the tenant PostgreSQL service."""

from __future__ import annotations

from typing import Sequence

from .migration_cli import run_fixed_migration_cli
from .migration_sets import TENANT_SERVICE
from .provisioning_specs import TENANT_PROVISIONING_SPEC


TENANT_ADMIN_DSN_ENVIRONMENT = "OFARM_TENANT_PROVISIONING_PG_ADMIN_DSN"
TENANT_MIGRATOR_DSN_ENVIRONMENT = "OFARM_TENANT_MIGRATOR_DSN"
TENANT_RESOLVER_PASSWORD_ENVIRONMENT = "OFARM_TENANT_IDENTITY_RESOLVER_PASSWORD"


def main(argv: Sequence[str] | None = None) -> int:
    return run_fixed_migration_cli(
        service=TENANT_SERVICE,
        spec=TENANT_PROVISIONING_SPEC,
        admin_dsn_environment=TENANT_ADMIN_DSN_ENVIRONMENT,
        migrator_dsn_environment=TENANT_MIGRATOR_DSN_ENVIRONMENT,
        transition_login_password_environment=(
            TENANT_RESOLVER_PASSWORD_ENVIRONMENT
        ),
        argv=argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
