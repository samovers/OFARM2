"""Fixed command adapter for one bounded security-audit reader page."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from typing import Protocol

import psycopg

from deployment.postgresql.security_audit_query import (
    AcknowledgedSecurityAuditQuery,
    SecurityAuditQueryControlUnavailable,
    SecurityAuditQueryCursor,
    SecurityAuditQueryFailed,
    SecurityAuditQueryOutcomeUnknown,
    SecurityAuditQueryRefused,
    SecurityAuditQueryRunner,
)


CONTROL_DSN_ENVIRONMENT = "OFARM_SECURITY_AUDIT_CONTROL_PG_DSN"
READER_DSN_ENVIRONMENT = "OFARM_SECURITY_AUDIT_READER_PG_DSN"

_REFUSED = "security-audit query was refused\n"
_INVALID = "security-audit query command is invalid\n"
_UNAVAILABLE = (
    "security-audit query control route is unavailable; no commit was sent\n"
)
_UNKNOWN = (
    "security-audit query access-intent outcome is unknown; no query was sent; "
    "do not retry automatically\n"
)
_QUERY_FAILED = (
    "security-audit query intent committed but no complete report is available; "
    "do not retry automatically\n"
)
_REPORT_FAILED = (
    "security-audit query completed but reporting failed; "
    "do not retry automatically\n"
)


class _Runner(Protocol):
    def run(
        self,
        control_conninfo: str,
        reader_conninfo: str,
        cursor: SecurityAuditQueryCursor | None,
    ) -> AcknowledgedSecurityAuditQuery: ...


class _BinaryOutput(Protocol):
    def write(self, value: bytes) -> int: ...

    def flush(self) -> None: ...


class _TextOutput(Protocol):
    def write(self, value: str) -> int: ...

    def flush(self) -> None: ...


def _fail(stderr: _TextOutput, exit_code: int, line: str) -> int:
    written = stderr.write(line)
    if type(written) is not int or written != len(line):
        raise OSError("security-audit query diagnostic write was incomplete")
    stderr.flush()
    return exit_code


def _validated_conninfo(
    environ: Mapping[str, str],
    name: str,
) -> str:
    value = environ.get(name)
    if type(value) is not str or not value.strip():
        raise ValueError("security-audit query conninfo is absent")
    psycopg.conninfo.conninfo_to_dict(value)
    return value


def _validated_cursor(
    argv: Sequence[str],
) -> SecurityAuditQueryCursor | None:
    if len(argv) == 0:
        return None
    if (
        len(argv) == 2
        and type(argv[0]) is str
        and argv[0] == "--cursor"
        and type(argv[1]) is str
    ):
        return SecurityAuditQueryCursor.parse(argv[1])
    raise ValueError("security-audit query arguments are invalid")


def run_fixed_security_audit_query_cli(
    *,
    argv: Sequence[str],
    environ: Mapping[str, str],
    stdout: _BinaryOutput,
    stderr: _TextOutput,
    runner: _Runner,
) -> int:
    """Execute the closed bounded-query protocol through explicit sinks."""

    try:
        cursor = _validated_cursor(argv)
        control_conninfo = _validated_conninfo(
            environ, CONTROL_DSN_ENVIRONMENT
        )
        reader_conninfo = _validated_conninfo(environ, READER_DSN_ENVIRONMENT)
    except Exception:
        return _fail(stderr, 2, _INVALID)

    try:
        acknowledged = runner.run(control_conninfo, reader_conninfo, cursor)
    except SecurityAuditQueryRefused:
        return _fail(stderr, 1, _REFUSED)
    except SecurityAuditQueryControlUnavailable:
        return _fail(stderr, 3, _UNAVAILABLE)
    except SecurityAuditQueryOutcomeUnknown:
        return _fail(stderr, 4, _UNKNOWN)
    except SecurityAuditQueryFailed:
        return _fail(stderr, 5, _QUERY_FAILED)
    # Deliberately no catch-all: the production runner classifies every
    # ordinary exception from its external steps by internal state.  This
    # adapter cannot truthfully invent that state for a nonconforming runner.

    try:
        written = stdout.write(acknowledged.report_bytes)
        if type(written) is not int or written != len(acknowledged.report_bytes):
            raise OSError("security-audit query report write was incomplete")
        stdout.flush()
    except Exception:
        return _fail(stderr, 6, _REPORT_FAILED)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    actual_argv = tuple(sys.argv[1:] if argv is None else argv)
    return run_fixed_security_audit_query_cli(
        argv=actual_argv,
        environ=os.environ,
        stdout=sys.stdout.buffer,
        stderr=sys.stderr,
        runner=SecurityAuditQueryRunner(),
    )


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "CONTROL_DSN_ENVIRONMENT",
    "READER_DSN_ENVIRONMENT",
    "main",
    "run_fixed_security_audit_query_cli",
)
