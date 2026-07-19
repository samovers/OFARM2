"""Preflight the repository-fixed tenant PostgreSQL migration set."""

from .migration_sets import TENANT_SERVICE, preflight_main


def main() -> int:
    return preflight_main(TENANT_SERVICE)


if __name__ == "__main__":
    raise SystemExit(main())
