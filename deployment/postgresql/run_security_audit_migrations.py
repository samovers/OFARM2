"""Dedicated release entry point for the isolated security-audit service."""

from __future__ import annotations

from typing import Sequence

from .migration_cli import run_fixed_migration_cli
from .migration_sets import SECURITY_AUDIT_SERVICE
from .provisioning_specs import SECURITY_AUDIT_PROVISIONING_SPEC


AUDIT_ADMIN_DSN_ENVIRONMENT = "OFARM_SECURITY_AUDIT_PG_ADMIN_DSN"
AUDIT_MIGRATOR_DSN_ENVIRONMENT = "OFARM_SECURITY_AUDIT_MIGRATOR_DSN"


def main(argv: Sequence[str] | None = None) -> int:
    return run_fixed_migration_cli(
        service=SECURITY_AUDIT_SERVICE,
        spec=SECURITY_AUDIT_PROVISIONING_SPEC,
        admin_dsn_environment=AUDIT_ADMIN_DSN_ENVIRONMENT,
        migrator_dsn_environment=AUDIT_MIGRATOR_DSN_ENVIRONMENT,
        argv=argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
