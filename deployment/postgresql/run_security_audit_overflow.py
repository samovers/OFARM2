"""Fixed command adapter for one security-audit overflow closure attempt."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from typing import Protocol

import psycopg

from deployment.postgresql.security_audit_overflow import (
    CompletedSecurityAuditOverflowRun,
    SecurityAuditOverflowOutcomeUnknown,
    SecurityAuditOverflowRefused,
    SecurityAuditOverflowRunner,
    SecurityAuditOverflowUnavailable,
)


OVERFLOW_DSN_ENVIRONMENT = "OFARM_SECURITY_AUDIT_CONTROL_PG_DSN"

_REFUSED = "security-audit overflow closure was refused\n"
_INVALID = "security-audit overflow closure command is invalid\n"
_UNAVAILABLE = (
    "security-audit overflow closure is unavailable; no commit was sent\n"
)
_UNKNOWN = (
    "security-audit overflow closure outcome is unknown; "
    "do not retry automatically\n"
)
_REPORT_FAILED = (
    "security-audit overflow closure result reporting failed; "
    "do not retry automatically\n"
)


class _Runner(Protocol):
    def run(self, conninfo: str) -> CompletedSecurityAuditOverflowRun: ...


class _BinaryOutput(Protocol):
    def write(self, value: bytes) -> int: ...

    def flush(self) -> None: ...


class _TextOutput(Protocol):
    def write(self, value: str) -> int: ...

    def flush(self) -> None: ...


def _fail(stderr: _TextOutput, exit_code: int, line: str) -> int:
    written = stderr.write(line)
    if type(written) is not int or written != len(line):
        raise OSError(
            "security-audit overflow closure diagnostic write was incomplete"
        )
    stderr.flush()
    return exit_code


def _validated_conninfo(environ: Mapping[str, str]) -> str:
    value = environ.get(OVERFLOW_DSN_ENVIRONMENT)
    if type(value) is not str or not value.strip():
        raise ValueError("security-audit overflow closure conninfo is absent")
    psycopg.conninfo.conninfo_to_dict(value)
    return value


def run_fixed_security_audit_overflow_cli(
    *,
    argv: Sequence[str],
    environ: Mapping[str, str],
    stdout: _BinaryOutput,
    stderr: _TextOutput,
    runner: _Runner,
) -> int:
    """Execute the closed overflow-closure protocol through explicit sinks."""

    try:
        if len(argv) != 0:
            raise ValueError("security-audit overflow closure arguments are invalid")
        conninfo = _validated_conninfo(environ)
    except Exception:
        return _fail(stderr, 2, _INVALID)

    try:
        completed = runner.run(conninfo)
    except SecurityAuditOverflowRefused:
        return _fail(stderr, 1, _REFUSED)
    except SecurityAuditOverflowUnavailable:
        return _fail(stderr, 3, _UNAVAILABLE)
    except SecurityAuditOverflowOutcomeUnknown:
        return _fail(stderr, 4, _UNKNOWN)
    # Deliberately no catch-all: the production runner classifies every
    # supported external step from its actual state.  This adapter cannot
    # truthfully invent that state for a nonconforming injected runner.

    try:
        written = stdout.write(completed.report_bytes)
        if type(written) is not int or written != len(completed.report_bytes):
            raise OSError(
                "security-audit overflow closure report write was incomplete"
            )
        stdout.flush()
    except Exception:
        return _fail(stderr, 5, _REPORT_FAILED)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    actual_argv = tuple(sys.argv[1:] if argv is None else argv)
    return run_fixed_security_audit_overflow_cli(
        argv=actual_argv,
        environ=os.environ,
        stdout=sys.stdout.buffer,
        stderr=sys.stderr,
        runner=SecurityAuditOverflowRunner(),
    )


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "OVERFLOW_DSN_ENVIRONMENT",
    "main",
    "run_fixed_security_audit_overflow_cli",
)
