"""Closed command-line adapter for one fixed PostgreSQL migration lane."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence
from uuid import UUID

from .migration_runner import MigrationError, migrate_service
from .migration_sets import (
    MigrationService,
    MigrationSetError,
    load_authoritative_migration_set,
)
from .provisioning_specs import ProvisioningSpec


_PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def _execution_id(value: str) -> UUID:
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise argparse.ArgumentTypeError(
            "execution identity must be one canonical UUID"
        ) from exc
    if parsed.int == 0 or str(parsed) != value:
        raise argparse.ArgumentTypeError(
            "execution identity must be one canonical non-nil UUID"
        )
    return parsed


def run_fixed_migration_cli(
    *,
    service: MigrationService,
    spec: ProvisioningSpec,
    admin_dsn_environment: str,
    migrator_dsn_environment: str,
    argv: Sequence[str] | None = None,
) -> int:
    """Run one repository-fixed service without accepting route selection."""

    parser = argparse.ArgumentParser(
        description=(
            f"Apply the immutable {service.identity} migration set. "
            "Database routes come only from the two named environment variables."
        )
    )
    parser.add_argument("--release-identity", required=True)
    parser.add_argument("--execution-id", required=True, type=_execution_id)
    arguments = parser.parse_args(argv)

    admin_dsn = os.environ.get(admin_dsn_environment)
    migrator_dsn = os.environ.get(migrator_dsn_environment)
    if not admin_dsn or not migrator_dsn:
        parser.exit(
            2,
            "migration refused: exact admin and migrator DSN environment "
            "variables are both required\n",
        )
    try:
        migration_set = load_authoritative_migration_set(_PACKAGE_ROOT, service)
        report = migrate_service(
            admin_dsn=admin_dsn,
            migrator_dsn=migrator_dsn,
            spec=spec,
            migration_set=migration_set,
            release_identity=arguments.release_identity,
            execution_id=arguments.execution_id,
        )
    except (MigrationSetError, MigrationError) as exc:
        parser.exit(1, f"migration refused: {exc}\n")
    print(
        json.dumps(
            report.manifest(),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


__all__ = ["run_fixed_migration_cli"]
