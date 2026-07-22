"""Preflight the repository-fixed security-audit PostgreSQL migration set."""

from .migration_sets import SECURITY_AUDIT_SERVICE, preflight_main


def main() -> int:
    return preflight_main(SECURITY_AUDIT_SERVICE)


if __name__ == "__main__":
    raise SystemExit(main())
