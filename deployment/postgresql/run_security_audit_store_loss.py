"""Fixed command adapter for one security-audit store-loss recovery attempt."""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

import psycopg

from deployment.postgresql.security_audit_store_loss import (
    SecurityAuditStoreLossInputError,
    SecurityAuditStoreLossOutcomeUnknown,
    SecurityAuditStoreLossRecoveryRunner,
    SecurityAuditStoreLossRefused,
    StoreLossRecoveryReport,
    StoreLossRecoveryRequest,
    StoreLossRecoverySecrets,
)


STORE_LOSS_ADMIN_DSN_ENVIRONMENT = "OFARM_SECURITY_AUDIT_PG_ADMIN_DSN"
STORE_LOSS_MIGRATOR_DSN_ENVIRONMENT = "OFARM_SECURITY_AUDIT_MIGRATOR_DSN"
STORE_LOSS_CONTROL_DSN_ENVIRONMENT = "OFARM_SECURITY_AUDIT_CONTROL_PG_DSN"
STORE_LOSS_PASSWORD_ENVIRONMENTS = (
    (
        "ofarm_migrator",
        "OFARM_SECURITY_AUDIT_MIGRATOR_LOGIN_PASSWORD",
    ),
    (
        "ofarm_security_authentication_producer_login",
        "OFARM_SECURITY_AUTHENTICATION_PRODUCER_LOGIN_PASSWORD",
    ),
    (
        "ofarm_security_request_router_producer_login",
        "OFARM_SECURITY_REQUEST_ROUTER_PRODUCER_LOGIN_PASSWORD",
    ),
    (
        "ofarm_security_audit_control_login",
        "OFARM_SECURITY_AUDIT_CONTROL_LOGIN_PASSWORD",
    ),
    (
        "ofarm_security_audit_reader_login",
        "OFARM_SECURITY_AUDIT_READER_LOGIN_PASSWORD",
    ),
    (
        "ofarm_security_audit_retention_login",
        "OFARM_SECURITY_AUDIT_RETENTION_LOGIN_PASSWORD",
    ),
    (
        "ofarm_security_audit_readiness_login",
        "OFARM_SECURITY_AUDIT_READINESS_LOGIN_PASSWORD",
    ),
)

_CANONICAL_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{6}Z"
)
_ARGUMENT_NAMES = (
    "--loss-start",
    "--release-identity",
    "--execution-id",
)
_INVALID = b"security-audit store-loss recovery command is invalid\n"
_REFUSED = (
    b"security-audit store-loss recovery was refused; "
    b"keep the target quarantined\n"
)
_UNKNOWN = (
    b"security-audit store-loss recovery outcome is unknown; "
    b"keep the target quarantined and do not retry\n"
)
_REPORT_FAILED = (
    b"security-audit store-loss recovery reporting failed; "
    b"keep the target quarantined and do not retry\n"
)


class _Runner(Protocol):
    def run(
        self,
        request: StoreLossRecoveryRequest,
        secret_carrier: StoreLossRecoverySecrets,
    ) -> StoreLossRecoveryReport: ...


class _BinaryOutput(Protocol):
    def write(self, value: bytes) -> int: ...

    def flush(self) -> None: ...


def _fail(stderr: _BinaryOutput, exit_code: int, line: bytes) -> int:
    try:
        written = stderr.write(line)
        if type(written) is int and written == len(line):
            stderr.flush()
    except Exception:
        pass
    return exit_code


def _parse_timestamp(value: str) -> datetime:
    if _CANONICAL_TIMESTAMP.fullmatch(value) is None:
        raise ValueError("store-loss loss-start timestamp is not canonical")
    return datetime.strptime(
        value,
        "%Y-%m-%dT%H:%M:%S.%fZ",
    ).replace(tzinfo=timezone.utc)


def _parse_execution_id(value: str) -> UUID:
    parsed = UUID(value)
    if parsed.int == 0 or str(parsed) != value:
        raise ValueError("store-loss execution identity is not canonical")
    return parsed


def _parse_request(argv: Sequence[str]) -> StoreLossRecoveryRequest:
    if len(argv) != 6 or any(type(value) is not str for value in argv):
        raise ValueError("store-loss arguments differ")
    observed: dict[str, str] = {}
    for index in range(0, 6, 2):
        name = argv[index]
        value = argv[index + 1]
        if name not in _ARGUMENT_NAMES or name in observed or not value:
            raise ValueError("store-loss arguments differ")
        observed[name] = value
    if set(observed) != set(_ARGUMENT_NAMES):
        raise ValueError("store-loss arguments differ")
    return StoreLossRecoveryRequest(
        loss_start=_parse_timestamp(observed["--loss-start"]),
        release_identity=observed["--release-identity"],
        execution_id=_parse_execution_id(observed["--execution-id"]),
    )


def _required_environment(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name)
    if type(value) is not str or not value.strip():
        raise ValueError("store-loss environment is incomplete")
    return value


def _secret_carrier(environ: Mapping[str, str]) -> StoreLossRecoverySecrets:
    admin_dsn = _required_environment(
        environ,
        STORE_LOSS_ADMIN_DSN_ENVIRONMENT,
    )
    migrator_dsn = _required_environment(
        environ,
        STORE_LOSS_MIGRATOR_DSN_ENVIRONMENT,
    )
    control_dsn = _required_environment(
        environ,
        STORE_LOSS_CONTROL_DSN_ENVIRONMENT,
    )
    for value in (admin_dsn, migrator_dsn, control_dsn):
        psycopg.conninfo.conninfo_to_dict(value)
    passwords = tuple(
        (role_name, _required_environment(environ, environment_name))
        for role_name, environment_name in STORE_LOSS_PASSWORD_ENVIRONMENTS
    )
    return StoreLossRecoverySecrets(
        admin_dsn=admin_dsn,
        migrator_dsn=migrator_dsn,
        control_dsn=control_dsn,
        login_passwords=passwords,
    )


def run_fixed_security_audit_store_loss_cli(
    *,
    argv: Sequence[str],
    environ: Mapping[str, str],
    stdout: _BinaryOutput,
    stderr: _BinaryOutput,
    runner: _Runner,
) -> int:
    """Execute the closed recovery command through explicit output sinks."""

    try:
        request = _parse_request(argv)
        secret_carrier = _secret_carrier(environ)
    except Exception:
        return _fail(stderr, 2, _INVALID)
    try:
        report = runner.run(request, secret_carrier)
    except SecurityAuditStoreLossInputError:
        return _fail(stderr, 2, _INVALID)
    except SecurityAuditStoreLossRefused:
        return _fail(stderr, 3, _REFUSED)
    except SecurityAuditStoreLossOutcomeUnknown:
        return _fail(stderr, 4, _UNKNOWN)
    except Exception:
        return _fail(stderr, 3, _REFUSED)
    try:
        report_bytes = report.report_bytes
        written = stdout.write(report_bytes)
        if type(written) is not int or written != len(report_bytes):
            raise OSError("store-loss recovery report write was incomplete")
        stdout.flush()
    except Exception:
        return _fail(stderr, 5, _REPORT_FAILED)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    actual_argv = tuple(sys.argv[1:] if argv is None else argv)
    return run_fixed_security_audit_store_loss_cli(
        argv=actual_argv,
        environ=os.environ,
        stdout=sys.stdout.buffer,
        stderr=sys.stderr.buffer,
        runner=SecurityAuditStoreLossRecoveryRunner(),
    )


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "STORE_LOSS_ADMIN_DSN_ENVIRONMENT",
    "STORE_LOSS_CONTROL_DSN_ENVIRONMENT",
    "STORE_LOSS_MIGRATOR_DSN_ENVIRONMENT",
    "STORE_LOSS_PASSWORD_ENVIRONMENTS",
    "main",
    "run_fixed_security_audit_store_loss_cli",
)
