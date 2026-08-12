"""Fixed command adapter for one security-audit logical retention batch."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from typing import Protocol

import psycopg

from deployment.postgresql.security_audit_retention import (
    AcknowledgedSecurityAuditRetention,
    SecurityAuditRetentionOutcomeUnknown,
    SecurityAuditRetentionRefused,
    SecurityAuditRetentionRunner,
    SecurityAuditRetentionUnavailable,
)


RETENTION_DSN_ENVIRONMENT = "OFARM_SECURITY_AUDIT_RETENTION_PG_DSN"

_REFUSED = "security-audit retention was refused\n"
_INVALID = "security-audit retention command is invalid\n"
_UNAVAILABLE = "security-audit retention is unavailable; no commit was sent\n"
_UNKNOWN = (
    "security-audit retention outcome is unknown; do not retry automatically\n"
)
_REPORT_FAILED = (
    "security-audit retention committed but reporting failed; "
    "do not retry automatically\n"
)


class _Runner(Protocol):
    def run(self, conninfo: str) -> AcknowledgedSecurityAuditRetention: ...


class _BinaryOutput(Protocol):
    def write(self, value: bytes) -> int: ...

    def flush(self) -> None: ...


class _TextOutput(Protocol):
    def write(self, value: str) -> int: ...

    def flush(self) -> None: ...


def _fail(stderr: _TextOutput, exit_code: int, line: str) -> int:
    written = stderr.write(line)
    if type(written) is not int or written != len(line):
        raise OSError("security-audit retention diagnostic write was incomplete")
    stderr.flush()
    return exit_code


def run_fixed_security_audit_retention_cli(
    *,
    argv: Sequence[str],
    environ: Mapping[str, str],
    stdout: _BinaryOutput,
    stderr: _TextOutput,
    runner: _Runner,
) -> int:
    """Execute the closed command protocol through explicit testable sinks."""

    if len(argv) != 0:
        return _fail(stderr, 2, _INVALID)

    conninfo = environ.get(RETENTION_DSN_ENVIRONMENT)
    if conninfo is None or not conninfo.strip():
        return _fail(stderr, 2, _INVALID)
    try:
        psycopg.conninfo.conninfo_to_dict(conninfo)
    except Exception:
        return _fail(stderr, 2, _INVALID)

    try:
        acknowledged = runner.run(conninfo)
    except SecurityAuditRetentionRefused:
        return _fail(stderr, 1, _REFUSED)
    except SecurityAuditRetentionUnavailable:
        return _fail(stderr, 3, _UNAVAILABLE)
    except SecurityAuditRetentionOutcomeUnknown:
        return _fail(stderr, 4, _UNKNOWN)
    except Exception:
        return _fail(stderr, 4, _UNKNOWN)

    try:
        written = stdout.write(acknowledged.report_bytes)
        if type(written) is not int or written != len(acknowledged.report_bytes):
            raise OSError("security-audit retention report write was incomplete")
        stdout.flush()
    except Exception:
        return _fail(stderr, 5, _REPORT_FAILED)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    actual_argv = tuple(sys.argv[1:] if argv is None else argv)
    return run_fixed_security_audit_retention_cli(
        argv=actual_argv,
        environ=os.environ,
        stdout=sys.stdout.buffer,
        stderr=sys.stderr,
        runner=SecurityAuditRetentionRunner(),
    )


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "RETENTION_DSN_ENVIRONMENT",
    "main",
    "run_fixed_security_audit_retention_cli",
)
